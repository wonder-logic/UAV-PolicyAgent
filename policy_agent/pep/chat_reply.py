from __future__ import annotations

import json
import re
from typing import Any
from urllib import error, request

from policy_agent.api.schemas import DroneCatalogEntry, PolicyRequest
from policy_agent.config import Settings
from policy_agent.utils.logging import get_logger

logger = get_logger(__name__)

INTERNAL_WARNING_PREFIXES = (
    "LLM evaluator not configured",
    "Deterministic Part 107 safeguards",
)

MISSING_ATTRIBUTE_LABELS = {
    "remote_id_available": "whether Remote ID will be active",
    "anti_collision_lights": "anti-collision lighting",
    "controlled_airspace authorization evidence": "controlled-airspace authorization",
    "operation_type": "the operation type",
    "pilot_certification_provided": "whether the pilot is covered by a valid Part 107 certificate",
    "altitude_ft": "the planned altitude",
    "visual_line_of_sight": "whether the drone will stay within direct visual line of sight",
    "over_moving_vehicles": "whether the route includes sustained flight over moving vehicles",
    "drone_model_or_weight": "the aircraft model or verified weight",
    "local_restrictions_known": "local site restrictions or approval",
}

POLICY_CHAT_SYSTEM_PROMPT = """You are UAVGuard Policy Agent.

Write like a careful, conversational assistant in the style of ChatGPT, but stay grounded.

Rules:
- Use only the verified facts and policy evidence provided.
- Do not invent rules, facts, or approvals.
- If required information is missing, say that clearly and ask only the single next question provided.
- Do not mention internal fields, JSON, implementation details, LLM configuration, or system behavior.
- Avoid robotic phrases such as "I updated the structured request."
- Prefer 2 to 4 short paragraphs.
- Answer the user's question directly before giving supporting detail.
"""


def _join_naturally(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _humanize_missing_attributes(missing_attributes: list[str]) -> list[str]:
    return [MISSING_ATTRIBUTE_LABELS.get(attribute, attribute.replace("_", " ")) for attribute in missing_attributes]


def _clean_snippet(text: str, *, section: str | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    cleaned = cleaned.replace("## ", "").replace("# ", "")
    if section and cleaned.casefold().startswith(section.casefold()):
        cleaned = cleaned[len(section) :].lstrip(" :-")
    first_sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0].strip()
    return first_sentence or cleaned


def _core_mission_summary(
    *,
    policy_request: PolicyRequest,
    drone_profile: DroneCatalogEntry | None,
) -> str | None:
    aircraft = None
    if drone_profile is not None:
        aircraft = f"a {drone_profile.manufacturer} {drone_profile.model_name}"
    elif policy_request.drone_manufacturer and policy_request.drone_model:
        aircraft = f"a {policy_request.drone_manufacturer} {policy_request.drone_model}"
    elif policy_request.drone_weight_grams is not None:
        aircraft = f"an aircraft weighing about {policy_request.drone_weight_grams:.0f} grams"

    mission_parts: list[str] = []
    if aircraft:
        mission_parts.append(aircraft)
    if policy_request.operation_type != "unknown":
        mission_parts.append(f"on a {policy_request.operation_type.replace('_', ' ')} mission")
    if policy_request.origin_location:
        mission_parts.append(f"near {policy_request.origin_location}")
    if policy_request.altitude_ft is not None:
        mission_parts.append(f"at {policy_request.altitude_ft:.0f} feet")
    if policy_request.night_operation is True:
        mission_parts.append("at night")
    elif policy_request.night_operation is False:
        mission_parts.append("during the day")

    if not mission_parts:
        return None
    return " ".join(mission_parts)


def _compliance_summary(policy_request: PolicyRequest) -> list[str]:
    details: list[str] = []
    if policy_request.visual_line_of_sight is True:
        details.append("visual line of sight maintained")
    elif policy_request.visual_line_of_sight is False:
        details.append("a beyond-visual-line-of-sight profile")

    if policy_request.remote_id_available is True:
        details.append("active Remote ID")
    elif policy_request.remote_id_available is False:
        details.append("no Remote ID")

    if policy_request.pilot_certification_provided is True:
        details.append("pilot certification already covered")
    elif policy_request.pilot_certification_provided is False:
        details.append("missing pilot certification")

    if policy_request.controlled_airspace is True:
        details.append("controlled airspace involved")
    elif policy_request.controlled_airspace is False:
        details.append("no controlled airspace indicated")

    return details


def _user_visible_warnings(preview_decision: dict[str, Any] | None) -> list[str]:
    if preview_decision is None:
        return []
    warnings: list[str] = []
    for warning in preview_decision.get("warnings", []):
        rendered = str(warning).strip()
        if not rendered:
            continue
        if any(rendered.startswith(prefix) for prefix in INTERNAL_WARNING_PREFIXES):
            continue
        warnings.append(rendered)
    return warnings


def _decision_status(preview_decision: dict[str, Any] | None) -> str | None:
    if preview_decision is None:
        return None
    status = preview_decision.get("uavguard_status")
    return str(status) if status else None


def _lowercase_initial(text: str) -> str:
    if not text:
        return text
    return text[:1].lower() + text[1:]


def _opening_sentence(*, intent: str, status: str | None, next_question: str | None) -> str:
    if next_question:
        if intent == "eligibility":
            return "I can see why you're asking, but I can't give you a clean yes yet."
        if intent == "why":
            return "The short answer is that the outcome still turns on one missing detail."
        if intent == "missing":
            return "You are close, but one detail is still doing most of the work here."
        return "I can help you work this through, but I still need one key detail."

    if status == "APPROVED":
        return "Based on what you've told me, this looks likely approvable under the policy material I have."
    if status == "DENIED":
        return "Based on what you've told me, I would not treat this as approvable as described."
    if intent == "why":
        return "Here is the main reason the answer is still not fully clean."
    return "From the policy material I have, this is close, but it still needs a closer look."


def _policy_reasoning_paragraph(
    *,
    policy_request: PolicyRequest,
    preview_decision: dict[str, Any] | None,
) -> str | None:
    if preview_decision is None:
        return None

    sentences: list[str] = []
    if policy_request.night_operation is True:
        if (
            policy_request.remote_id_available is True
            and policy_request.visual_line_of_sight is True
            and policy_request.pilot_certification_provided is True
        ):
            sentences.append(
                "For the night portion of this mission, the main policy checks are Remote ID, visual line of sight, and pilot certification, and those pieces are already covered in what you've told me."
            )
        else:
            sentences.append(
                "For the night portion of this mission, the main policy checks are Remote ID, visual line of sight, and pilot certification."
            )

    if policy_request.controlled_airspace is True:
        if policy_request.controlled_airspace_authorization_provided is True:
            sentences.append("If the route touches controlled airspace, you have already indicated authorization is in place.")
        else:
            sentences.append(
                "If any part of the route enters controlled airspace, that becomes a separate authorization issue."
            )

    explanation = str(preview_decision.get("explanation") or "").strip()
    if policy_request.altitude_ft is not None and "400 feet" in explanation:
        if policy_request.altitude_ft <= 400:
            sentences.append(
                f"Your stated altitude of {policy_request.altitude_ft:.0f} feet is within the 400-foot ceiling in the policy baseline."
            )
        else:
            sentences.append(
                f"Your stated altitude of {policy_request.altitude_ft:.0f} feet is above the 400-foot ceiling in the policy baseline."
            )

    obligations = [str(item).strip() for item in preview_decision.get("obligations", []) if str(item).strip()]
    if any("local site approval" in item.casefold() or "local flight restrictions" in item.casefold() for item in obligations):
        sentences.append("The biggest practical caveat I still see is local site approval or local operating restrictions.")
    elif any("controlled-airspace authorization" in item.casefold() or "controlled airspace authorization" in item.casefold() for item in obligations):
        sentences.append("The biggest practical caveat I still see is controlled-airspace authorization.")
    elif any("anti-collision lighting" in item.casefold() for item in obligations):
        sentences.append("The biggest practical caveat I still see is anti-collision lighting for the night flight.")

    if not sentences:
        return explanation or None
    return " ".join(sentences)


def _next_step_paragraph(
    *,
    preview_decision: dict[str, Any] | None,
    next_question: str | None,
    knowledge_follow_up_questions: list[str],
    knowledge_warnings: list[str],
) -> str | None:
    if next_question is not None:
        missing_attributes = preview_decision.get("missing_attributes", []) if preview_decision else []
        missing_labels = _humanize_missing_attributes([str(item) for item in missing_attributes])[:3]
        if missing_labels:
            lead_in = "The only thing I still need before I can give you a grounded answer is" if len(missing_labels) == 1 else (
                "What keeps this from being a clean yes right now is that I still need confirmation on"
            )
            return (
                f"{lead_in} {_join_naturally(missing_labels)}. "
                f"The next thing I need from you is: {next_question}"
            )
        return f"The next thing I need from you is: {next_question}"

    if preview_decision is None:
        return None

    obligations = [str(item).strip() for item in preview_decision.get("obligations", []) if str(item).strip()]
    advice = [str(item).strip() for item in preview_decision.get("advice", []) if str(item).strip()]
    visible_warnings = _user_visible_warnings(preview_decision)

    follow_up_sentences: list[str] = []
    if obligations:
        follow_up_sentences.append(
            f"The main follow-up I would keep in mind is to {_lowercase_initial(obligations[0].rstrip('.'))}."
        )
    if advice:
        follow_up_sentences.append(f"I would also {_lowercase_initial(advice[0].rstrip('.'))}.")
    if visible_warnings:
        follow_up_sentences.append(visible_warnings[0].rstrip(".") + ".")
    elif knowledge_warnings:
        follow_up_sentences.append(knowledge_warnings[0].rstrip(".") + ".")
    if knowledge_follow_up_questions:
        follow_up_sentences.append(
            f"If you want a tighter grounded review after that, the next useful detail would be: {knowledge_follow_up_questions[0]}"
        )

    if not follow_up_sentences:
        return None
    return " ".join(follow_up_sentences[:2])


def _fallback_reply(
    *,
    message: str,
    policy_request: PolicyRequest,
    drone_profile: DroneCatalogEntry | None,
    catalog_warnings: list[str],
    preview_decision: dict[str, Any] | None,
    next_question: str | None,
    knowledge_warnings: list[str],
    knowledge_follow_up_questions: list[str],
    follow_up_acknowledgement: str | None,
) -> str:
    lowered_message = message.casefold()
    if any(token in lowered_message for token in ("what am i missing", "what's missing", "what else do you need")):
        intent = "missing"
    elif any(token in lowered_message for token in ("why", "how come", "what makes")):
        intent = "why"
    elif any(token in lowered_message for token in ("can i", "could i", "am i allowed", "is this allowed", "is it okay")):
        intent = "eligibility"
    else:
        intent = "update"

    paragraphs: list[str] = []
    opening = _opening_sentence(intent=intent, status=_decision_status(preview_decision), next_question=next_question)

    mission_summary = _core_mission_summary(policy_request=policy_request, drone_profile=drone_profile)
    compliance_details = _compliance_summary(policy_request)

    first_paragraph: str
    is_brief_follow_up = follow_up_acknowledgement is not None and len(message.strip().split()) <= 4
    if is_brief_follow_up:
        first_paragraph = follow_up_acknowledgement or "Thanks."
        if compliance_details:
            first_paragraph += f" At this point I have {_join_naturally(compliance_details)}."
    else:
        first_paragraph = opening
        if follow_up_acknowledgement:
            first_paragraph += f" {follow_up_acknowledgement}"
        if mission_summary:
            first_paragraph += f" Right now I'm treating this as {mission_summary}."
        if compliance_details:
            first_paragraph += f" I also have {_join_naturally(compliance_details)}."
    paragraphs.append(first_paragraph)

    reasoning = _policy_reasoning_paragraph(policy_request=policy_request, preview_decision=preview_decision)
    if reasoning:
        paragraphs.append(reasoning)

    next_step = _next_step_paragraph(
        preview_decision=preview_decision,
        next_question=next_question,
        knowledge_follow_up_questions=knowledge_follow_up_questions,
        knowledge_warnings=knowledge_warnings,
    )
    if next_step:
        paragraphs.append(next_step)

    if catalog_warnings:
        paragraphs.append(f"One thing to double-check: {catalog_warnings[0]}")

    return "\n\n".join(paragraph.strip() for paragraph in paragraphs if paragraph.strip())


def _llm_chat_enabled(settings: Settings) -> bool:
    return bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)


def _render_llm_user_prompt(
    *,
    message: str,
    policy_request: PolicyRequest,
    verified_facts: list[str],
    next_question: str | None,
    preview_decision: dict[str, Any] | None,
    catalog_warnings: list[str],
    knowledge_warnings: list[str],
    knowledge_follow_up_questions: list[str],
) -> str:
    policy_payload = policy_request.model_dump(mode="json")
    decision_payload = preview_decision or {}
    filtered_payload = {
        "status": decision_payload.get("uavguard_status"),
        "decision": decision_payload.get("decision"),
        "explanation": decision_payload.get("explanation"),
        "missing_attributes": decision_payload.get("missing_attributes", []),
        "obligations": decision_payload.get("obligations", []),
        "advice": decision_payload.get("advice", []),
        "warnings": _user_visible_warnings(preview_decision),
        "citations": decision_payload.get("citations", [])[:2],
    }
    return (
        "Operator message:\n"
        f"{message}\n\n"
        "Verified facts:\n"
        f"{json.dumps(verified_facts, indent=2)}\n\n"
        "Structured mission state:\n"
        f"{json.dumps(policy_payload, indent=2)}\n\n"
        "Grounded policy evidence:\n"
        f"{json.dumps(filtered_payload, indent=2)}\n\n"
        "Catalog warnings:\n"
        f"{json.dumps(catalog_warnings, indent=2)}\n\n"
        "Knowledge-context warnings:\n"
        f"{json.dumps(knowledge_warnings, indent=2)}\n\n"
        "Optional knowledge follow-up questions that improve groundedness but do not always block the decision:\n"
        f"{json.dumps(knowledge_follow_up_questions, indent=2)}\n\n"
        "Single next question to ask if something is still missing:\n"
        f"{next_question or ''}\n\n"
        "Write the assistant reply now."
    )


def _generate_llm_reply(
    *,
    settings: Settings,
    message: str,
    policy_request: PolicyRequest,
    verified_facts: list[str],
    next_question: str | None,
    preview_decision: dict[str, Any] | None,
    catalog_warnings: list[str],
    knowledge_warnings: list[str],
    knowledge_follow_up_questions: list[str],
) -> str | None:
    if not _llm_chat_enabled(settings):
        return None

    llm_base_url = settings.llm_base_url
    llm_api_key = settings.llm_api_key
    if llm_base_url is None or llm_api_key is None:
        return None

    endpoint = f"{llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": POLICY_CHAT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _render_llm_user_prompt(
                    message=message,
                    policy_request=policy_request,
                    verified_facts=verified_facts,
                    next_question=next_question,
                    preview_decision=preview_decision,
                    catalog_warnings=catalog_warnings,
                    knowledge_warnings=knowledge_warnings,
                    knowledge_follow_up_questions=knowledge_follow_up_questions,
                ),
            },
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=raw_body,
        headers={
            "Authorization": f"Bearer {llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=settings.llm_timeout_seconds) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:  # pragma: no cover - network dependent
        logger.warning("Policy chat LLM reply failed, falling back to deterministic response: %s", exc)
        return None

    content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
    rendered = str(content).strip()
    return rendered or None


def build_grounded_chat_reply(
    *,
    settings: Settings,
    message: str,
    policy_request: PolicyRequest,
    drone_profile: DroneCatalogEntry | None,
    catalog_warnings: list[str],
    preview_decision: dict[str, Any] | None,
    next_question: str | None,
    verified_facts: list[str],
    knowledge_warnings: list[str],
    knowledge_follow_up_questions: list[str],
    follow_up_acknowledgement: str | None,
) -> str:
    llm_reply = _generate_llm_reply(
        settings=settings,
        message=message,
        policy_request=policy_request,
        verified_facts=verified_facts,
        next_question=next_question,
        preview_decision=preview_decision,
        catalog_warnings=catalog_warnings,
        knowledge_warnings=knowledge_warnings,
        knowledge_follow_up_questions=knowledge_follow_up_questions,
    )
    if llm_reply:
        return llm_reply

    return _fallback_reply(
        message=message,
        policy_request=policy_request,
        drone_profile=drone_profile,
        catalog_warnings=catalog_warnings,
        preview_decision=preview_decision,
        next_question=next_question,
        knowledge_warnings=knowledge_warnings,
        knowledge_follow_up_questions=knowledge_follow_up_questions,
        follow_up_acknowledgement=follow_up_acknowledgement,
    )

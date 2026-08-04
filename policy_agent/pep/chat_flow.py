from __future__ import annotations

import re
from dataclasses import dataclass

from policy_agent.api.schemas import (
    DroneCatalogEntry,
    PolicyChatDecisionSummary,
    PolicyChatEvaluationStage,
    PolicyChatResponse,
    PolicyKnowledgeSource,
    PolicyRequest,
)
from policy_agent.config import Settings
from policy_agent.drone_catalog.repository import DroneCatalogRepository
from policy_agent.evaluation.rule_evaluator import evaluate_request_attributes
from policy_agent.pep.chat_reply import build_grounded_chat_reply
from policy_agent.pep.conversation_service import build_follow_up_questions
from policy_agent.pep.knowledge_pipeline import compute_grounding_scores
from policy_agent.utils.json_utils import unique_in_order

ALTITUDE_PATTERN = re.compile(r"\b(\d{2,4})\s*(?:ft|feet|foot)\b", re.IGNORECASE)
SPEED_PATTERN = re.compile(r"\b(\d{1,3})\s*(?:mph|miles per hour)\b", re.IGNORECASE)
WEIGHT_PATTERN = re.compile(r"\b(\d{2,5})\s*(?:g|grams)\b", re.IGNORECASE)
TIME_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
AFFIRMATIVE_ANSWER_PATTERN = re.compile(
    r"^(?:yes|y|yeah|yep|correct|affirmative|we do|i do|it is|it does|we have|i have|that's right|that is right)\b",
    re.IGNORECASE,
)
NEGATIVE_ANSWER_PATTERN = re.compile(
    r"^(?:no|n|nope|nah|negative|we do not|we don't|i do not|i don't|it is not|it isn't|it does not|it doesn't)\b",
    re.IGNORECASE,
)
LOCATION_PATTERNS = (
    re.compile(r"\bnear\s+([^,.\n]+?)(?=,| and | at \d|\.|$)", re.IGNORECASE),
    re.compile(r"\bfrom\s+([^,.\n]+?)(?=,| and | at \d|\.|$)", re.IGNORECASE),
    re.compile(r"\bat\s+([^,.\n]+?)(?=,| and |\.|$)", re.IGNORECASE),
)
DESTINATION_PATTERN = re.compile(r"\bto\s+([^,.\n]+?)(?=,| and |\.|$)", re.IGNORECASE)
FOLLOW_UP_BOOL_FIELDS = {
    "remote_id_available": "remote_id_available",
    "anti_collision_lights": "anti_collision_lights",
    "controlled_airspace authorization evidence": "controlled_airspace_authorization_provided",
    "pilot_certification_provided": "pilot_certification_provided",
    "visual_line_of_sight": "visual_line_of_sight",
    "over_moving_vehicles": "over_moving_vehicles",
    "local_restrictions_known": "local_restrictions_known",
}
FOLLOW_UP_ACK_LABELS = {
    "remote_id_available": "Remote ID",
    "anti_collision_lights": "anti-collision lighting",
    "controlled_airspace authorization evidence": "controlled-airspace authorization",
    "pilot_certification_provided": "the required pilot certification",
    "visual_line_of_sight": "visual line of sight",
    "over_moving_vehicles": "flight over moving vehicles",
    "local_restrictions_known": "local site approval",
}


@dataclass(slots=True)
class ChatExtraction:
    updated_request: PolicyRequest
    extracted_fields: list[str]
    drone_profile: DroneCatalogEntry | None
    catalog_warnings: list[str]
    follow_up_acknowledgement: str | None


def _join_naturally(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _apply_text_flag(
    *,
    lowered_message: str,
    updates: dict[str, object],
    field_name: str,
    positive_signals: tuple[str, ...],
    negative_signals: tuple[str, ...],
) -> None:
    if any(signal in lowered_message for signal in negative_signals):
        updates[field_name] = False
        return
    if any(signal in lowered_message for signal in positive_signals):
        updates[field_name] = True


def _extract_operation_type(lowered_message: str) -> str | None:
    if "public safety" in lowered_message or "emergency response" in lowered_message:
        return "public_safety"
    if "research" in lowered_message or "mapping" in lowered_message or "survey" in lowered_message:
        return "research"
    if "commercial" in lowered_message or "inspection" in lowered_message or "client" in lowered_message:
        return "commercial"
    if "recreational" in lowered_message or "hobby" in lowered_message:
        return "recreational"
    return None


def _extract_time_descriptor(message: str, lowered_message: str) -> str | None:
    if "night" in lowered_message or "after sunset" in lowered_message or "after dark" in lowered_message:
        return "night"
    if "daytime" in lowered_message or "during the day" in lowered_message or "before sunset" in lowered_message:
        return "day"

    time_match = TIME_PATTERN.search(message)
    if time_match is None:
        return None

    hour = int(time_match.group(1))
    meridiem = time_match.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return "night" if hour >= 21 or hour < 6 else "day"


def _extract_location(message: str) -> str | None:
    for pattern in LOCATION_PATTERNS:
        match = pattern.search(message)
        if match is None:
            continue
        candidate = match.group(1).strip(" .?")
        lowered_candidate = candidate.casefold()
        if (
            candidate
            and not TIME_PATTERN.fullmatch(candidate)
            and not ALTITUDE_PATTERN.fullmatch(candidate)
            and not SPEED_PATTERN.fullmatch(candidate)
            and " feet" not in lowered_candidate
            and " ft" not in lowered_candidate
            and " mph" not in lowered_candidate
        ):
            return candidate
    return None


def _extract_destination(message: str) -> str | None:
    match = DESTINATION_PATTERN.search(message)
    if match is None:
        return None
    candidate = match.group(1).strip(" .?")
    lowered_candidate = candidate.casefold()
    if not candidate:
        return None
    if ALTITUDE_PATTERN.fullmatch(candidate) or SPEED_PATTERN.fullmatch(candidate) or TIME_PATTERN.fullmatch(candidate):
        return None
    if " feet" in lowered_candidate or " ft" in lowered_candidate or " mph" in lowered_candidate:
        return None
    return candidate


def _extract_mission_purpose(lowered_message: str) -> str | None:
    if "research" in lowered_message:
        return "Research mission"
    if "mapping" in lowered_message:
        return "Mapping mission"
    if "survey" in lowered_message:
        return "Survey mission"
    if "inspection" in lowered_message:
        return "Inspection mission"
    if "training" in lowered_message:
        return "Training mission"
    return None


def _follow_up_acknowledgement(*, missing_attribute: str, value: bool) -> str:
    label = FOLLOW_UP_ACK_LABELS.get(missing_attribute, missing_attribute.replace("_", " "))
    if value:
        return f"Thanks, that confirms {label}."
    return f"Thanks, that tells me {label} is not currently in place."


def _resolve_short_follow_up_answer(
    *,
    message: str,
    current_request: PolicyRequest,
) -> tuple[dict[str, object], str | None]:
    normalized_message = " ".join(message.strip().split())
    if not normalized_message:
        return {}, None

    answer_value: bool | None = None
    if AFFIRMATIVE_ANSWER_PATTERN.match(normalized_message):
        answer_value = True
    elif NEGATIVE_ANSWER_PATTERN.match(normalized_message):
        answer_value = False

    if answer_value is None:
        return {}, None

    missing_attributes = evaluate_request_attributes(current_request).missing_attributes
    if not missing_attributes:
        return {}, None

    target_attribute = missing_attributes[0]
    field_name = FOLLOW_UP_BOOL_FIELDS.get(target_attribute)
    if field_name is None:
        return {}, None

    return {field_name: answer_value}, _follow_up_acknowledgement(
        missing_attribute=target_attribute,
        value=answer_value,
    )


def _find_catalog_match_in_message(
    message: str,
    drone_catalog: DroneCatalogRepository,
) -> DroneCatalogEntry | None:
    normalized_message = " ".join(message.casefold().split())
    matches = []
    for entry in drone_catalog.load_entries():
        manufacturer = " ".join(entry.manufacturer.casefold().split())
        model_name = " ".join(entry.model_name.casefold().split())
        if manufacturer in normalized_message and model_name in normalized_message:
            matches.append(entry)
        elif model_name in normalized_message:
            matches.append(entry)

    if not matches:
        return None
    matches.sort(key=lambda item: len(item.model_name), reverse=True)
    return matches[0]


def extract_policy_chat_request(
    *,
    message: str,
    current_request: PolicyRequest,
    drone_catalog: DroneCatalogRepository,
) -> ChatExtraction:
    lowered_message = message.casefold()
    updates: dict[str, object] = {}
    follow_up_acknowledgement: str | None = None

    enriched_current_request, _, _ = drone_catalog.enrich_request(current_request)
    follow_up_updates, follow_up_acknowledgement = _resolve_short_follow_up_answer(
        message=message,
        current_request=enriched_current_request,
    )
    updates.update(follow_up_updates)

    catalog_match = _find_catalog_match_in_message(message, drone_catalog)
    if catalog_match is not None:
        updates["drone_model_id"] = catalog_match.model_id
        updates["drone_manufacturer"] = catalog_match.manufacturer
        updates["drone_model"] = catalog_match.model_name

    operation_type = _extract_operation_type(lowered_message)
    if operation_type is not None:
        updates["operation_type"] = operation_type

    altitude_match = ALTITUDE_PATTERN.search(message)
    if altitude_match is not None:
        updates["altitude_ft"] = float(altitude_match.group(1))

    speed_match = SPEED_PATTERN.search(message)
    if speed_match is not None:
        updates["speed_mph"] = float(speed_match.group(1))

    if current_request.drone_model is None and current_request.drone_weight_grams is None:
        weight_match = WEIGHT_PATTERN.search(message)
        if weight_match is not None:
            updates["drone_weight_grams"] = float(weight_match.group(1))

    time_descriptor = _extract_time_descriptor(message, lowered_message)
    if time_descriptor is not None:
        updates["intended_flight_time"] = time_descriptor
        updates["night_operation"] = time_descriptor == "night"

    location = _extract_location(message)
    if location is not None:
        updates["origin_location"] = location
        updates["live_location"] = location

    destination = _extract_destination(message)
    if destination is not None:
        updates["destination_location"] = destination

    mission_purpose = _extract_mission_purpose(lowered_message)
    if mission_purpose is not None:
        updates["mission_purpose"] = mission_purpose

    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="visual_line_of_sight",
        positive_signals=(
            "stay within visual line of sight",
            "remain within visual line of sight",
            " vlos",
            "visual line of sight",
        ),
        negative_signals=("bvlos", "beyond visual line of sight", "not within visual line of sight"),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="over_people",
        positive_signals=("over people", "over a crowd", "over spectators"),
        negative_signals=(
            "not over people",
            "not flying over people",
            "clear of people",
            "no people below",
            "not flying over any people",
        ),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="over_moving_vehicles",
        positive_signals=("over moving vehicles", "over traffic", "over cars", "moving vehicles below"),
        negative_signals=(
            "not over moving vehicles",
            "not flying over moving vehicles",
            "not flying over people or moving vehicles",
            "not over people or moving vehicles",
            "clear of traffic",
            "no moving vehicles below",
        ),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="controlled_airspace",
        positive_signals=("controlled airspace", "class b", "class c", "class d", "class e"),
        negative_signals=("class g", "uncontrolled airspace"),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="controlled_airspace_authorization_provided",
        positive_signals=("have authorization", "authorization provided", "laanc authorization", "laanc approved"),
        negative_signals=("no authorization", "without authorization", "do not have authorization"),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="remote_id_available",
        positive_signals=(
            "remote id active",
            "remote id is active",
            "remote id available",
            "standard remote id",
            "remote id enabled",
        ),
        negative_signals=("no remote id", "without remote id", "remote id unavailable"),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="pilot_certification_provided",
        positive_signals=("part 107", "remote pilot certificate", "pilot certification provided"),
        negative_signals=("no part 107", "without a remote pilot certificate", "no pilot certificate"),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="anti_collision_lights",
        positive_signals=("anti-collision lights", "anti collision lights", "lighting visible", "strobe active"),
        negative_signals=("no anti-collision lights", "without anti-collision lights", "no strobe"),
    )
    _apply_text_flag(
        lowered_message=lowered_message,
        updates=updates,
        field_name="local_restrictions_known",
        positive_signals=(
            "local restrictions checked",
            "site approval confirmed",
            "site approval is confirmed",
            "local site approval confirmed",
            "local site approval is confirmed",
            "local approval confirmed",
            "local approval is confirmed",
        ),
        negative_signals=("local restrictions unknown", "site approval pending"),
    )

    if any(token in lowered_message for token in ("over moving vehicles", "moving vehicles", "traffic", "cars below")):
        if any(
            signal in lowered_message
            for signal in (
                "not over moving vehicles",
                "not flying over moving vehicles",
                "not flying over people or moving vehicles",
                "not over people or moving vehicles",
                "clear of traffic",
            )
        ):
            updates["additional_context"] = current_request.additional_context or None
            updates["additional_context"] = (
                "Mission remains clear of moving vehicles."
                if updates["additional_context"] is None
                else f"{updates['additional_context']} Mission remains clear of moving vehicles."
            )

    merged_request = current_request.model_copy(update=updates)
    enriched_request, drone_profile, catalog_warnings = drone_catalog.enrich_request(merged_request)

    return ChatExtraction(
        updated_request=enriched_request,
        extracted_fields=sorted(updates.keys()),
        drone_profile=drone_profile,
        catalog_warnings=catalog_warnings,
        follow_up_acknowledgement=follow_up_acknowledgement,
    )


def _build_verified_facts(
    *,
    policy_request: PolicyRequest,
    drone_profile: DroneCatalogEntry | None,
) -> list[str]:
    facts: list[str] = []

    if drone_profile is not None:
        facts.append(f"Aircraft: {drone_profile.manufacturer} {drone_profile.model_name}")
    elif policy_request.drone_manufacturer and policy_request.drone_model:
        facts.append(f"Aircraft: {policy_request.drone_manufacturer} {policy_request.drone_model}")
    elif policy_request.drone_weight_grams is not None:
        facts.append(f"Aircraft weight: {policy_request.drone_weight_grams:.0f} g")

    if policy_request.operation_type != "unknown":
        facts.append(f"Operation type: {policy_request.operation_type.replace('_', ' ')}")
    if policy_request.origin_location:
        facts.append(f"Location: {policy_request.origin_location}")
    if policy_request.altitude_ft is not None:
        facts.append(f"Altitude: {policy_request.altitude_ft:.0f} ft")
    if policy_request.night_operation is not None:
        facts.append("Night operation" if policy_request.night_operation else "Day operation")
    if policy_request.visual_line_of_sight is not None:
        facts.append("VLOS maintained" if policy_request.visual_line_of_sight else "BVLOS or VLOS exception")
    if policy_request.remote_id_available is not None:
        facts.append("Remote ID available" if policy_request.remote_id_available else "Remote ID unavailable")
    if policy_request.pilot_certification_provided is not None:
        facts.append(
            "Pilot certification provided"
            if policy_request.pilot_certification_provided
            else "Pilot certification not provided"
        )
    if policy_request.controlled_airspace is not None:
        facts.append(
            "Controlled airspace" if policy_request.controlled_airspace else "No controlled airspace indicated"
        )
    if policy_request.over_moving_vehicles is not None:
        facts.append(
            "Flight over moving vehicles"
            if policy_request.over_moving_vehicles
            else "No sustained flight over moving vehicles"
        )

    return facts[:8]


def build_policy_chat_response(
    *,
    settings: Settings,
    message: str,
    extracted_request: PolicyRequest,
    extracted_fields: list[str],
    drone_profile: DroneCatalogEntry | None,
    catalog_warnings: list[str],
    knowledge_context_used: bool,
    knowledge_verified_facts: list[str],
    knowledge_warnings: list[str],
    knowledge_gaps: list[str],
    knowledge_follow_up_questions: list[str],
    knowledge_blocking_questions: list[str],
    follow_up_acknowledgement: str | None,
    preview_decision: dict[str, object] | None,
    evaluation_stage: PolicyChatEvaluationStage,
    knowledge_agent_called: bool,
    knowledge_source: PolicyKnowledgeSource,
    verified_mission_context: dict[str, object] | None,
    knowledge_request: dict[str, object] | None,
    knowledge_response: dict[str, object] | None,
    spatial_constraints: list[dict[str, object]],
    simulator_package: dict[str, object] | None,
    errors: list[str],
    knowledge_request_preview: dict[str, object] | None,
    simulator_grid_preview: dict[str, object] | None,
) -> PolicyChatResponse:
    evaluation = evaluate_request_attributes(extracted_request)
    missing_attributes = evaluation.missing_attributes
    policy_questions = build_follow_up_questions(missing_attributes)
    if policy_questions:
        next_question = policy_questions[0]
    elif knowledge_blocking_questions:
        next_question = knowledge_blocking_questions[0]
    else:
        next_question = None
    verified_facts = unique_in_order(
        _build_verified_facts(policy_request=extracted_request, drone_profile=drone_profile) + knowledge_verified_facts
    )

    resolved_preview_decision = dict(preview_decision) if preview_decision is not None else None
    mission_score, accuracy_score = compute_grounding_scores(
        preview_decision=resolved_preview_decision,
        knowledge_context_used=knowledge_context_used,
        knowledge_blocker_count=len(knowledge_blocking_questions),
        knowledge_refinement_count=len(knowledge_follow_up_questions),
        knowledge_warning_count=len(knowledge_warnings),
    )
    if resolved_preview_decision is not None:
        resolved_preview_decision["mission_score"] = mission_score
        resolved_preview_decision["accuracy_score"] = accuracy_score
        resolved_preview_decision["knowledge_context_used"] = knowledge_context_used

    final_decision_ready = evaluation_stage == PolicyChatEvaluationStage.FINAL and not knowledge_blocking_questions
    decision_summary = None
    if resolved_preview_decision is not None:
        decision_summary = PolicyChatDecisionSummary(
            status=resolved_preview_decision.get("uavguard_status"),
            summary=resolved_preview_decision.get("explanation"),
            explanation=resolved_preview_decision.get("explanation"),
            rule_results=list(resolved_preview_decision.get("rule_results", [])),
            warnings=list(resolved_preview_decision.get("warnings", [])),
            obligations=list(resolved_preview_decision.get("obligations", [])),
            citations=list(resolved_preview_decision.get("citations", [])),
            mission_score=resolved_preview_decision.get("mission_score"),
            accuracy_score=resolved_preview_decision.get("accuracy_score"),
            confidence=resolved_preview_decision.get("confidence"),
            matched_policies=list(resolved_preview_decision.get("matched_policies", [])),
        )

    return PolicyChatResponse(
        assistant_message=build_grounded_chat_reply(
            settings=settings,
            message=message,
            policy_request=extracted_request,
            drone_profile=drone_profile,
            catalog_warnings=catalog_warnings,
            preview_decision=resolved_preview_decision,
            next_question=next_question,
            verified_facts=verified_facts,
            knowledge_warnings=knowledge_warnings,
            knowledge_follow_up_questions=knowledge_follow_up_questions,
            follow_up_acknowledgement=follow_up_acknowledgement,
        ),
        evaluation_stage=evaluation_stage,
        knowledge_agent_called=knowledge_agent_called,
        knowledge_source=knowledge_source,
        policy_request=extracted_request,
        verified_mission_context=verified_mission_context,
        missing_fields=missing_attributes,
        grounded_facts=verified_facts,
        decision=decision_summary,
        knowledge_request=knowledge_request,
        knowledge_response=knowledge_response,
        spatial_constraints=spatial_constraints,
        simulator_package=simulator_package,
        errors=errors,
        extracted_fields=unique_in_order(extracted_fields),
        missing_attributes=missing_attributes,
        next_question=next_question,
        ready_for_decision=not missing_attributes,
        final_decision_ready=final_decision_ready,
        verified_facts=verified_facts,
        catalog_warnings=catalog_warnings,
        knowledge_context_used=knowledge_context_used,
        knowledge_warnings=knowledge_warnings,
        knowledge_gaps=knowledge_gaps,
        knowledge_follow_up_questions=knowledge_follow_up_questions,
        preview_decision=resolved_preview_decision,
        knowledge_request_preview=knowledge_request_preview,
        simulator_grid_preview=simulator_grid_preview,
    )

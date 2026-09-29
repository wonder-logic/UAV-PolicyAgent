from __future__ import annotations

import re
from typing import Any

from policy_agent.api.schemas import PolicyRequest
from policy_agent.config import Settings
from policy_agent.evaluation.llm_evaluator import OpenAICompatibleLLMEvaluator
from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.pdp.combining_algorithms import deny_overrides
from policy_agent.retrieval.citations import citations_from_chunks
from policy_agent.utils.json_utils import unique_in_order

DENY_PHRASES = ("must not", "shall not", "not allowed", "not permitted", "prohibited", "may not", "cannot")
ALLOW_PHRASES = ("may operate", "is permitted", "are permitted", "allowed", "authorized")
REQUIREMENT_PHRASES = ("require", "requires", "must", "shall", "needed", "provide", "maintain", "confirm")
MAX_LIMIT_PHRASES = ("maximum", "must not exceed", "shall not exceed", "no higher than", "not exceed")


class HybridEvaluator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_evaluator = OpenAICompatibleLLMEvaluator(settings)

    def evaluate(
        self,
        policy_request: PolicyRequest,
        retrieved_chunks: list[RetrievedPolicyChunk],
        missing_attributes: list[str],
    ) -> tuple[dict[str, Any] | None, bool]:
        heuristic_payload, contradictory = self._heuristic_evaluate(
            policy_request=policy_request,
            retrieved_chunks=retrieved_chunks,
            missing_attributes=missing_attributes,
        )

        llm_payload = self.llm_evaluator.evaluate(policy_request, retrieved_chunks, missing_attributes)
        if llm_payload is None:
            heuristic_payload["warnings"] = unique_in_order(
                list(heuristic_payload["warnings"])
                + ["LLM evaluator not configured; using conservative rule-based reasoning."]
            )
            return heuristic_payload, contradictory

        llm_decision = llm_payload.get("decision")
        if llm_decision not in {"PERMIT", "DENY", "NOT_APPLICABLE", "INDETERMINATE"}:
            heuristic_payload["warnings"] = unique_in_order(
                list(heuristic_payload["warnings"]) + ["LLM evaluator returned an invalid decision value."]
            )
            return heuristic_payload, contradictory

        combined_decision = deny_overrides(
            [heuristic_payload["decision"], llm_decision],
            missing_attributes,
            max(
                len(heuristic_payload["matched_policies"]),
                len(llm_payload.get("matched_policies", [])),
            ),
        )

        merged_payload = {
            "decision": combined_decision,
            "matched_policies": unique_in_order(
                list(heuristic_payload.get("matched_policies", [])) + list(llm_payload.get("matched_policies", []))
            ),
            "obligations": unique_in_order(
                list(heuristic_payload.get("obligations", [])) + list(llm_payload.get("obligations", []))
            ),
            "advice": unique_in_order(list(heuristic_payload.get("advice", [])) + list(llm_payload.get("advice", []))),
            "warnings": unique_in_order(
                list(heuristic_payload.get("warnings", [])) + list(llm_payload.get("warnings", []))
            ),
            "missing_attributes": unique_in_order(
                list(heuristic_payload.get("missing_attributes", [])) + list(llm_payload.get("missing_attributes", []))
            ),
            "citations": llm_payload.get("citations") or heuristic_payload.get("citations", []),
            "explanation": llm_payload.get("explanation") or heuristic_payload.get("explanation", ""),
            "confidence": llm_payload.get("confidence", heuristic_payload.get("confidence", "LOW")),
        }
        return merged_payload, contradictory

    def _heuristic_evaluate(
        self,
        policy_request: PolicyRequest,
        retrieved_chunks: list[RetrievedPolicyChunk],
        missing_attributes: list[str],
    ) -> tuple[dict[str, Any], bool]:
        if not retrieved_chunks:
            return {
                "decision": "NOT_APPLICABLE",
                "matched_policies": [],
                "obligations": [],
                "advice": [],
                "warnings": [],
                "missing_attributes": missing_attributes,
                "citations": [],
                "explanation": "No policy chunks matched the submitted request attributes.",
                "confidence": "LOW",
            }, False

        policy_decisions: list[str] = []
        decisive_chunks: list[RetrievedPolicyChunk] = []
        relevant_chunks: list[RetrievedPolicyChunk] = []
        explanations: list[str] = []
        contradictory = False

        for chunk in retrieved_chunks:
            assessment = self._assess_chunk(policy_request, chunk)
            if not assessment["relevant"]:
                continue

            relevant_chunks.append(chunk)
            policy_decisions.append(assessment["decision"])
            explanations.extend(assessment["reasons"])
            contradictory = contradictory or assessment["contradictory"]

            if assessment["decision"] in {"DENY", "PERMIT"}:
                decisive_chunks.append(chunk)

        final_decision = deny_overrides(
            policy_decisions=policy_decisions,
            missing_attributes=missing_attributes,
            relevant_policy_count=len(relevant_chunks),
        )

        if final_decision == "NOT_APPLICABLE":
            explanation = "Retrieved policy chunks did not apply to the submitted request."
        elif explanations:
            explanation = " ".join(unique_in_order(explanations))
        else:
            explanation = (
                "Retrieved policy context was relevant but insufficient for a definitive authorization result."
            )

        confidence = "LOW"
        if final_decision == "DENY" and len(decisive_chunks) >= 1:
            confidence = "MEDIUM" if len(decisive_chunks) == 1 else "HIGH"
        elif final_decision == "PERMIT" and decisive_chunks and not missing_attributes:
            confidence = "MEDIUM"

        citation_source = decisive_chunks or relevant_chunks[:3]
        relevance_label = (
            "Retrieved policy evidence supporting the decision"
            if final_decision in {"PERMIT", "DENY"}
            else "Retrieved policy context used during review"
        )
        matched_policies = unique_in_order(
            [f"{chunk.document}{f'#{chunk.section}' if chunk.section else ''}" for chunk in relevant_chunks]
        )
        return {
            "decision": final_decision,
            "matched_policies": matched_policies,
            "obligations": [],
            "advice": [],
            "warnings": [],
            "missing_attributes": missing_attributes,
            "citations": [
                citation.model_dump() for citation in citations_from_chunks(citation_source, relevance_label)
            ],
            "explanation": explanation,
            "confidence": confidence,
        }, contradictory

    def _assess_chunk(self, policy_request: PolicyRequest, chunk: RetrievedPolicyChunk) -> dict[str, Any]:
        text = chunk.text.lower()
        relevant = False
        decision = "NOT_APPLICABLE"
        reasons: list[str] = []

        explicit_allow = any(phrase in text for phrase in ALLOW_PHRASES)
        explicit_deny = any(phrase in text for phrase in DENY_PHRASES)
        has_requirements = any(phrase in text for phrase in REQUIREMENT_PHRASES)
        contradictory = explicit_allow and explicit_deny

        def register(candidate_decision: str, reason: str) -> None:
            nonlocal decision, relevant
            relevant = True
            reasons.append(reason)
            if candidate_decision == "DENY":
                decision = "DENY"
            elif candidate_decision == "PERMIT" and decision != "DENY":
                decision = "PERMIT"
            elif decision == "NOT_APPLICABLE":
                decision = "INDETERMINATE"

        if policy_request.night_operation and "night" in text:
            if explicit_deny:
                register("DENY", "Retrieved policy text prohibits the requested night operation.")
            elif "remote id" in text and policy_request.remote_id_available is False:
                register("DENY", "Retrieved policy text requires Remote ID for the requested night operation.")
            elif (
                "anti-collision" in text or "anticollision" in text
            ) and policy_request.anti_collision_lights is False:
                register(
                    "DENY", "Retrieved policy text requires anti-collision lighting for the requested night operation."
                )
            elif (
                "pilot" in text or "certification" in text or "part 107" in text
            ) and policy_request.pilot_certification_provided is False:
                register("DENY", "Retrieved policy text requires pilot certification for the requested mission.")
            elif ("visual line of sight" in text or "vlos" in text) and policy_request.visual_line_of_sight is False:
                register("DENY", "Retrieved policy text requires visual line of sight for the requested mission.")
            elif (
                has_requirements
                and policy_request.remote_id_available is True
                and policy_request.visual_line_of_sight is True
                and policy_request.anti_collision_lights is not False
                and (
                    policy_request.operation_type not in {"commercial", "research"}
                    or policy_request.pilot_certification_provided is True
                )
            ):
                register(
                    "PERMIT",
                    "Retrieved policy text describes night-operation requirements and the submitted mission indicates those conditions are satisfied.",
                )
            elif explicit_allow:
                register(
                    "PERMIT",
                    "Retrieved policy text explicitly allows the requested night operation when the stated conditions are met.",
                )
            else:
                register(
                    "INDETERMINATE",
                    "Retrieved policy text is relevant to night operations but does not fully resolve the request.",
                )

        if policy_request.over_people and "people" in text:
            if explicit_deny or "without" in text:
                register(
                    "DENY", "Retrieved policy text prohibits operations over people under the submitted conditions."
                )
            elif explicit_allow:
                register("PERMIT", "Retrieved policy text includes an explicit allowance for operations over people.")
            else:
                register(
                    "INDETERMINATE",
                    "Retrieved policy text discusses operations over people but remains incomplete for a safe decision.",
                )

        if policy_request.controlled_airspace and "controlled airspace" in text:
            if explicit_deny:
                register(
                    "DENY",
                    "Retrieved policy text prohibits the requested controlled-airspace mission without additional authorization.",
                )
            elif "authorization" in text and policy_request.controlled_airspace_authorization_provided is False:
                register(
                    "DENY",
                    "Retrieved policy text requires controlled airspace authorization and the request indicates it is unavailable.",
                )
            elif "authorization" in text and has_requirements:
                register(
                    "INDETERMINATE",
                    "Retrieved policy text requires controlled airspace authorization evidence that was not supplied.",
                )
            elif "authorization" in text and policy_request.controlled_airspace_authorization_provided is True:
                register(
                    "PERMIT",
                    "Retrieved policy text requires controlled-airspace authorization and the submitted mission indicates it is already in place.",
                )
            elif explicit_allow:
                register("PERMIT", "Retrieved policy text explicitly allows the controlled-airspace operation.")

        if "remote id" in text:
            if policy_request.remote_id_available is False and (has_requirements or explicit_deny):
                register(
                    "DENY", "Retrieved policy text requires Remote ID and the request indicates it is unavailable."
                )
            elif policy_request.remote_id_available is True and has_requirements:
                register(
                    "PERMIT",
                    "Retrieved policy text includes a Remote ID requirement and the submitted mission indicates it will be met.",
                )

        if "anti-collision" in text or "anticollision" in text:
            if policy_request.anti_collision_lights is False and (has_requirements or explicit_deny):
                register(
                    "DENY",
                    "Retrieved policy text requires anti-collision lighting and the request indicates it is unavailable.",
                )
            elif policy_request.anti_collision_lights is True and has_requirements:
                register(
                    "PERMIT",
                    "Retrieved policy text includes an anti-collision-lighting requirement and the submitted mission indicates it will be met.",
                )

        if "visual line of sight" in text or "vlos" in text:
            if policy_request.visual_line_of_sight is False and (has_requirements or explicit_deny):
                register(
                    "DENY",
                    "Retrieved policy text requires visual line of sight and the request indicates that condition will not be met.",
                )
            elif policy_request.visual_line_of_sight is True and has_requirements:
                register(
                    "PERMIT",
                    "Retrieved policy text requires visual line of sight and the submitted mission indicates that condition will be met.",
                )

        if (
            ("pilot" in text or "certification" in text or "part 107" in text)
            and policy_request.operation_type in {"commercial", "research"}
        ):
            if policy_request.pilot_certification_provided is False and (has_requirements or explicit_deny):
                register("DENY", "Retrieved policy text requires pilot certification for the submitted operation type.")
            elif policy_request.pilot_certification_provided is True and has_requirements:
                register(
                    "PERMIT",
                    "Retrieved policy text requires pilot certification for the submitted operation type and the submitted mission indicates that condition will be met.",
                )

        if policy_request.altitude_ft is not None and ("altitude" in text or "feet" in text or "ft" in text):
            limit_match = re.search(r"(\d{2,4})\s*(?:feet|foot|ft)", text)
            if limit_match and any(phrase in text for phrase in MAX_LIMIT_PHRASES):
                limit = float(limit_match.group(1))
                if policy_request.altitude_ft > limit:
                    register(
                        "DENY",
                        f"Retrieved policy text sets an altitude ceiling of {int(limit)} feet, which is below the requested altitude.",
                    )
                else:
                    if explicit_allow:
                        register(
                            "PERMIT",
                            f"Retrieved policy text includes an explicit allowance and the requested altitude stays within the {int(limit)}-foot limit.",
                        )
                    else:
                        register(
                            "PERMIT",
                            f"Retrieved policy text sets an altitude ceiling of {int(limit)} feet and the requested altitude stays within that limit.",
                        )

        if "local" in text or "campus" in text or "property" in text:
            if policy_request.local_restrictions_known is not True and has_requirements:
                register(
                    "INDETERMINATE",
                    "Retrieved policy text references local or property restrictions that still need confirmation.",
                )
            elif policy_request.local_restrictions_known is True and has_requirements:
                register(
                    "PERMIT",
                    "Retrieved policy text references local or property restrictions and the submitted mission indicates those checks were already confirmed.",
                )

        return {
            "relevant": relevant,
            "decision": decision,
            "reasons": unique_in_order(reasons),
            "contradictory": contradictory,
        }

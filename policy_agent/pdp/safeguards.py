from __future__ import annotations

from typing import Any, cast

from pydantic import ValidationError

from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.pdp.decision import PDPDecision
from policy_agent.pdp.decision_mapper import PDPDecisionValue, map_pdp_decision_to_status
from policy_agent.utils.json_utils import unique_in_order

VALID_PDP_DECISIONS = frozenset({"PERMIT", "DENY", "NOT_APPLICABLE", "INDETERMINATE"})


def _coerce_decision(value: object) -> PDPDecisionValue:
    if isinstance(value, str) and value in VALID_PDP_DECISIONS:
        return cast(PDPDecisionValue, value)
    return "INDETERMINATE"


def _base_payload(
    *,
    decision: str,
    explanation: str,
    confidence: str = "LOW",
    warnings: list[str] | None = None,
    missing_attributes: list[str] | None = None,
) -> dict[str, Any]:
    normalized_decision = _coerce_decision(decision)
    return {
        "decision": normalized_decision,
        "uavguard_status": map_pdp_decision_to_status(normalized_decision),
        "matched_policies": [],
        "obligations": [],
        "advice": [],
        "warnings": warnings or [],
        "missing_attributes": missing_attributes or [],
        "citations": [],
        "explanation": explanation,
        "confidence": confidence,
    }


def _normalize_payload(
    candidate_payload: dict[str, Any] | None, known_missing_attributes: list[str]
) -> dict[str, Any] | None:
    if candidate_payload is None:
        return None

    decision_value = _coerce_decision(candidate_payload.get("decision"))
    merged_payload = {
        "decision": decision_value,
        "uavguard_status": map_pdp_decision_to_status(decision_value),
        "matched_policies": candidate_payload.get("matched_policies", []),
        "obligations": candidate_payload.get("obligations", []),
        "advice": candidate_payload.get("advice", []),
        "warnings": candidate_payload.get("warnings", []),
        "missing_attributes": unique_in_order(
            list(candidate_payload.get("missing_attributes", [])) + known_missing_attributes
        ),
        "citations": candidate_payload.get("citations", []),
        "explanation": candidate_payload.get("explanation", ""),
        "confidence": candidate_payload.get("confidence", "LOW"),
    }
    try:
        return PDPDecision.model_validate(merged_payload).model_dump()
    except ValidationError:
        return None


def apply_safeguards(
    candidate_payload: dict[str, Any] | None,
    retrieved_chunks: list[RetrievedPolicyChunk],
    known_missing_attributes: list[str],
    *,
    contradictory_policy: bool = False,
) -> PDPDecision:
    if not retrieved_chunks:
        return PDPDecision.model_validate(
            _base_payload(
                decision="NOT_APPLICABLE",
                explanation="No retrieved policy context applied to the submitted request.",
                warnings=["No policy context was retrieved from the local policy repository."],
                missing_attributes=known_missing_attributes,
            )
        )

    payload = _normalize_payload(candidate_payload, known_missing_attributes)
    if payload is None:
        payload = _base_payload(
            decision="INDETERMINATE",
            explanation="The evaluator output was invalid or incomplete, so the Policy Agent defaulted to a conservative result.",
            warnings=["Evaluator output was invalid JSON or did not match the expected schema."],
            missing_attributes=known_missing_attributes,
        )

    payload["missing_attributes"] = unique_in_order(list(payload["missing_attributes"]) + known_missing_attributes)
    payload["warnings"] = unique_in_order(list(payload["warnings"]))

    if contradictory_policy:
        payload["decision"] = "INDETERMINATE"
        payload["confidence"] = "LOW"
        payload["warnings"] = unique_in_order(
            list(payload["warnings"]) + ["Retrieved policy text appears contradictory for this request."]
        )
        if not payload["explanation"]:
            payload["explanation"] = (
                "Retrieved policy text appeared contradictory, so the request requires human review."
            )

    if payload["decision"] == "PERMIT" and not payload["citations"]:
        payload["decision"] = "INDETERMINATE"
        payload["confidence"] = "LOW"
        payload["warnings"] = unique_in_order(
            list(payload["warnings"]) + ["PERMIT decision downgraded because no citations were supplied."]
        )

    if payload["decision"] == "PERMIT" and payload["missing_attributes"]:
        payload["decision"] = "INDETERMINATE"
        payload["confidence"] = "LOW"
        payload["warnings"] = unique_in_order(
            list(payload["warnings"]) + ["PERMIT decision downgraded because required attributes are still missing."]
        )

    if payload["decision"] == "PERMIT" and payload["confidence"] == "LOW":
        payload["decision"] = "INDETERMINATE"
        payload["warnings"] = unique_in_order(
            list(payload["warnings"]) + ["PERMIT decision downgraded because the evaluator confidence was LOW."]
        )

    if payload["decision"] == "DENY" and not payload["citations"]:
        payload["decision"] = "INDETERMINATE"
        payload["confidence"] = "LOW"
        payload["warnings"] = unique_in_order(
            list(payload["warnings"])
            + ["DENY decision downgraded because no supporting citation explained the denial."]
        )

    payload["uavguard_status"] = map_pdp_decision_to_status(_coerce_decision(payload["decision"]))
    return PDPDecision.model_validate(payload)

from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.pdp.decision import PDPDecision
from policy_agent.utils.json_utils import unique_in_order


def build_advice(
    policy_request: PolicyRequest,
    decision: PDPDecision,
    retrieved_chunks: list[RetrievedPolicyChunk],
) -> list[str]:
    advice: list[str] = []

    if retrieved_chunks:
        advice.append("Recheck FAA guidance before flight.")
    if policy_request.local_restrictions_known is not True:
        advice.append("Review local campus flight restrictions.")
    if decision.decision in {"INDETERMINATE", "NOT_APPLICABLE"}:
        advice.append("Have a human operator review this mission.")

    return unique_in_order(advice)

from __future__ import annotations

from typing import Literal

PDPDecisionValue = Literal["PERMIT", "DENY", "NOT_APPLICABLE", "INDETERMINATE"]
UAVGuardStatus = Literal["APPROVED", "DENIED", "NEEDS_REVIEW"]

DECISION_TO_STATUS: dict[PDPDecisionValue, UAVGuardStatus] = {
    "PERMIT": "APPROVED",
    "DENY": "DENIED",
    "NOT_APPLICABLE": "NEEDS_REVIEW",
    "INDETERMINATE": "NEEDS_REVIEW",
}


def map_pdp_decision_to_status(decision: PDPDecisionValue) -> UAVGuardStatus:
    return DECISION_TO_STATUS[decision]

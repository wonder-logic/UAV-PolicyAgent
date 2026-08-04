from __future__ import annotations

from policy_agent.pdp.decision_mapper import map_pdp_decision_to_status


def test_map_permit_to_approved():
    assert map_pdp_decision_to_status("PERMIT") == "APPROVED"


def test_map_deny_to_denied():
    assert map_pdp_decision_to_status("DENY") == "DENIED"


def test_map_indeterminate_to_needs_review():
    assert map_pdp_decision_to_status("INDETERMINATE") == "NEEDS_REVIEW"

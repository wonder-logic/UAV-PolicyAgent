from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.pep.enforcement_point import PolicyEnforcementPoint


def test_pdp_uses_builtin_policy_baseline_without_uploaded_documents(settings):
    pep = PolicyEnforcementPoint(settings)
    decision = pep.evaluate_request(PolicyRequest(operation_type="research", altitude_ft=300))

    assert decision.decision == "INDETERMINATE"
    assert decision.uavguard_status == "NEEDS_REVIEW"
    assert decision.citations


def test_pdp_returns_indeterminate_when_required_attributes_are_missing(settings, sample_policy_text):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    pep = PolicyEnforcementPoint(settings)
    pep.ingest_policies()

    decision = pep.evaluate_request(
        PolicyRequest(
            operation_type="research",
            altitude_ft=350,
            night_operation=True,
            remote_id_available=True,
            visual_line_of_sight=None,
            pilot_certification_provided=None,
        )
    )

    assert decision.decision == "INDETERMINATE"
    assert "visual_line_of_sight" in decision.missing_attributes
    assert "pilot_certification_provided" in decision.missing_attributes


def test_pdp_denies_altitude_above_400_feet_via_part107_safeguard(settings):
    pep = PolicyEnforcementPoint(settings)

    decision = pep.evaluate_request(
        PolicyRequest(
            operation_type="research",
            altitude_ft=450,
            night_operation=True,
            anti_collision_lights=True,
            remote_id_available=True,
            visual_line_of_sight=True,
            pilot_certification_provided=True,
        )
    )

    assert decision.decision == "DENY"
    assert decision.uavguard_status == "DENIED"
    assert any(citation.section == "14 CFR 107.51(b)" for citation in decision.citations)
    assert "400 feet above ground level" in decision.explanation

from __future__ import annotations

from datetime import date, datetime

from policy_agent.db.models import DroneProfile, ProfileCredential, UserPolicyProfile
from policy_agent.policies.engine import DeterministicPolicyEngine
from policy_agent.policies.verification import validate_citations
from policy_agent.schemas.common import VerificationStatus
from policy_agent.schemas.knowledge import KnowledgeAgentResponse, KnowledgeCellFact, KnowledgeMissionFact
from policy_agent.schemas.mission import MissionDetailsRead, MissionUpdate
from policy_agent.services.chat_service import merge_mission_updates
from policy_agent.services.profile_utils import is_credential_expired, profile_is_certificate_current


def build_mission(**overrides) -> MissionDetailsRead:
    payload = {
        "mission_id": "mission-1",
        "user_id": "user-1",
        "drone_id": "drone-1",
        "purpose": "Research shoreline mapping",
        "start_time": datetime(2026, 7, 23, 21, 0, 0),
        "end_time": datetime(2026, 7, 23, 22, 0, 0),
        "launch_location": {"type": "Feature", "geometry": None, "properties": {"label": "TAMU-CC waterfront"}},
        "operational_area": {"type": "Feature", "geometry": None, "properties": {"label": "Corpus Christi Bay"}},
        "maximum_altitude_agl_ft": 300,
        "maximum_distance_from_pilot_m": 600,
        "operation_over_people": False,
        "operation_over_moving_vehicles": False,
        "visual_line_of_sight": True,
        "night_operation": True,
        "expected_people_count": 0,
        "controlled_ground_area": True,
        "notes": "Baseline mission",
        "status": "ready_for_knowledge_agent",
        "latest_decision": None,
        "evaluation_timestamp": None,
        "created_at": datetime(2026, 7, 22, 10, 0, 0),
        "updated_at": datetime(2026, 7, 22, 10, 0, 0),
    }
    payload.update(overrides)
    return MissionDetailsRead.model_validate(payload)


def build_profile(**overrides) -> UserPolicyProfile:
    profile = UserPolicyProfile(
        id="profile-1",
        user_id="user-1",
        full_name="Avery Rhodes",
        email="avery@example.com",
        jurisdiction="US",
        operator_type="research",
        organization="TAMU-CC",
        preferred_units="imperial",
        remote_pilot_certificate_number="RPC-12345",
        remote_pilot_certificate_issue_date=date(2025, 1, 10),
        remote_pilot_certificate_expiration=date(2027, 1, 10),
        recurrent_training_completed=True,
        recurrent_training_date=date(2026, 4, 1),
    )
    profile.credentials = []
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


def build_drone(**overrides) -> DroneProfile:
    drone = DroneProfile(
        id="drone-1",
        owner_user_id="user-1",
        nickname="Research Mini",
        manufacturer="DJI",
        model="Mini 4 Pro",
        weight_grams=249,
        maximum_takeoff_weight_grams=249,
        category="small_uas",
        remote_id_type="standard",
        remote_id_serial_number="RID-001",
        anti_collision_lighting=True,
        light_visibility_statute_miles=3.5,
        maximum_endurance_minutes=34,
        maximum_operating_altitude_ft=400,
        verification_status="verified",
        is_default=True,
    )
    for key, value in overrides.items():
        setattr(drone, key, value)
    return drone


def build_knowledge(
    *, controlled_airspace: bool = False, cell_values: list[bool] | None = None
) -> KnowledgeAgentResponse:
    cells = []
    for index, value in enumerate(cell_values or [], start=1):
        cells.append(
            KnowledgeCellFact(
                cell_id=f"cell-{index}",
                facts=[
                    KnowledgeMissionFact(
                        category="controlled_airspace",
                        value=value,
                        source="test",
                        confidence=1.0,
                        verification_status=VerificationStatus.VERIFIED,
                    )
                ],
            )
        )

    return KnowledgeAgentResponse(
        request_id="request-1",
        mission_id="mission-1",
        mission_level_facts=[
            KnowledgeMissionFact(
                category="controlled_airspace",
                value=controlled_airspace,
                source="test",
                confidence=1.0,
                verification_status=VerificationStatus.VERIFIED,
            )
        ],
        cell_level_facts=cells,
        source="test",
        confidence=1.0,
        verification_status=VerificationStatus.VERIFIED,
    )


def build_credential(*, kind: str, credential_type: str, expiration: date | None = None) -> ProfileCredential:
    return ProfileCredential(
        id=f"{kind}-1",
        user_id="user-1",
        profile_id="profile-1",
        credential_kind=kind,
        credential_type=credential_type,
        identifier="AUTH-001",
        issuing_authority="FAA",
        issue_date=date(2026, 1, 1),
        expiration_date=expiration,
        verification_status="verified",
        restrictions=[],
        uploaded_document_reference=None,
        source="user",
    )


def test_profile_validation_and_certificate_dates():
    profile = build_profile()
    expired_credential = build_credential(kind="authorization", credential_type="LAANC", expiration=date(2026, 7, 1))

    assert profile_is_certificate_current(profile, on_date=date(2026, 7, 22)) is True
    assert is_credential_expired(expired_credential, on_date=date(2026, 7, 22)) is True


def test_mission_update_merge_preserves_existing_values():
    class MissionRecord:
        notes = "Keep this note"
        maximum_altitude_agl_ft = 250

    mission = MissionRecord()
    updates = MissionUpdate(maximum_altitude_agl_ft=320, notes=None)

    merge_mission_updates(mission=mission, updates=updates)

    assert mission.maximum_altitude_agl_ft == 320
    assert mission.notes == "Keep this note"


def test_policy_engine_denies_altitude_above_limit():
    engine = DeterministicPolicyEngine(policy_version="test")
    decision = engine.evaluate(
        mission=build_mission(maximum_altitude_agl_ft=450),
        profile=build_profile(),
        drone=build_drone(),
        knowledge_response=build_knowledge(controlled_airspace=False),
    )

    assert decision.decision == "DENIED"
    assert any(item.rule_id == "maximum_altitude" and item.result == "violated" for item in decision.policy_evaluations)


def test_policy_engine_flags_night_training_gap():
    engine = DeterministicPolicyEngine(policy_version="test")
    decision = engine.evaluate(
        mission=build_mission(night_operation=True),
        profile=build_profile(recurrent_training_completed=False),
        drone=build_drone(),
        knowledge_response=build_knowledge(controlled_airspace=False),
    )

    assert decision.decision == "DENIED"
    assert any(item.rule_id == "night_operations" and item.result == "violated" for item in decision.policy_evaluations)


def test_policy_engine_needs_review_for_controlled_airspace_without_authorization():
    engine = DeterministicPolicyEngine(policy_version="test")
    decision = engine.evaluate(
        mission=build_mission(),
        profile=build_profile(),
        drone=build_drone(),
        knowledge_response=build_knowledge(controlled_airspace=True),
    )

    assert decision.decision == "NEEDS_REVIEW"
    assert any(
        item.rule_id == "controlled_airspace" and item.result == "authorization_required"
        for item in decision.policy_evaluations
    )


def test_policy_engine_remote_id_rule_and_waiver_rule():
    engine = DeterministicPolicyEngine(policy_version="test")
    remote_id_review = engine.evaluate(
        mission=build_mission(),
        profile=build_profile(),
        drone=build_drone(remote_id_type=None, remote_id_serial_number=None),
        knowledge_response=build_knowledge(controlled_airspace=False),
    )
    waiver_deny = engine.evaluate(
        mission=build_mission(operation_over_people=True),
        profile=build_profile(),
        drone=build_drone(),
        knowledge_response=build_knowledge(controlled_airspace=False),
    )

    assert any(item.rule_id == "remote_id" and item.result == "unknown" for item in remote_id_review.policy_evaluations)
    assert waiver_deny.decision == "DENIED"
    assert any(
        item.rule_id == "operations_over_people" and item.result == "waiver_required"
        for item in waiver_deny.policy_evaluations
    )


def test_grid_cell_classification_and_citation_validation():
    engine = DeterministicPolicyEngine(policy_version="test")
    overall = engine.evaluate(
        mission=build_mission(),
        profile=build_profile(),
        drone=build_drone(),
        knowledge_response=build_knowledge(controlled_airspace=False, cell_values=[False, True]),
    )
    simulator_package = engine.build_simulator_package(
        mission=build_mission(),
        profile=build_profile(),
        drone=build_drone(),
        knowledge_response=build_knowledge(controlled_airspace=False, cell_values=[False, True]),
        overall_decision=overall,
    )

    statuses = {cell.cell_id: cell.status for cell in simulator_package.grid_cells}
    assert statuses["cell-1"] == "ALLOWED"
    assert statuses["cell-2"] == "REVIEW"
    assert validate_citations(overall.citations) == []

from __future__ import annotations

from datetime import date

import pytest

from policy_agent.core.exceptions import ExternalServiceError
from policy_agent.db import create_database
from policy_agent.integrations.llm_provider import MockLLMProvider
from policy_agent.schemas.auth import RegisterRequest
from policy_agent.schemas.common import VerificationStatus
from policy_agent.schemas.drone import DroneProfileCreate
from policy_agent.schemas.knowledge import KnowledgeAgentResponse, KnowledgeMissionFact
from policy_agent.schemas.mission import (
    MissionCreate,
    MissionEvaluationRequest,
    MissionUpdate,
    MissionUpdateExtraction,
)
from policy_agent.schemas.profile import UserPolicyProfileCreate
from policy_agent.services import ChatService, EvaluationService
from policy_agent.services.auth_service import AuthService
from policy_agent.services.drone_service import DroneService
from policy_agent.services.mission_service import MissionService
from policy_agent.services.profile_service import ProfileService


class ControlledAirspaceKnowledgeClient:
    def fetch_facts(self, request):
        return KnowledgeAgentResponse(
            request_id=request.request_id,
            mission_id=request.mission_id,
            mission_level_facts=[
                KnowledgeMissionFact(
                    category="controlled_airspace",
                    value=True,
                    source="mock",
                    confidence=1.0,
                    verification_status=VerificationStatus.VERIFIED,
                )
            ],
            source="mock",
            confidence=1.0,
            verification_status=VerificationStatus.VERIFIED,
        )


class TimeoutKnowledgeClient:
    def fetch_facts(self, request):
        raise ExternalServiceError("Knowledge Agent timed out")


class InvalidKnowledgeClient:
    def fetch_facts(self, request):
        return {"not": "a valid response"}


class UnsupportedExplanationLLM(MockLLMProvider):
    def generate_decision_explanation(self, *, mission, decision):  # noqa: D401
        return "This refers to 107.999 even though that section is not part of the trusted citation bundle."


class DeterministicExtractionLLM(MockLLMProvider):
    def extract_mission_update(self, *, message, mission):
        return MissionUpdateExtraction(
            updates=MissionUpdate(maximum_altitude_agl_ft=280, visual_line_of_sight=True),
            missing_fields=[],
            uncertain_fields=[],
            follow_up_question=None,
            reasoning_summary="Mock structured extraction",
        )


@pytest.fixture()
def service_context(settings):
    database = create_database(settings)
    database.create_all()
    session = database.session_factory()
    auth_service = AuthService(session, settings)
    auth = auth_service.register(
        RegisterRequest(
            full_name="Avery Rhodes",
            email="avery@example.com",
            password="ResearchPass123",
            organization="TAMU-CC",
        )
    )
    user = auth_service.authenticate_token(auth.access_token)
    ProfileService(session).create_profile(
        user,
        UserPolicyProfileCreate(
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
        ),
    )
    drone = DroneService(session).create_drone(
        user,
        DroneProfileCreate(
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
        ),
    )
    mission = MissionService(session).create_mission(
        user,
        MissionCreate(
            drone_id=drone.drone_id,
            purpose="Research shoreline mapping",
            start_time="2026-07-23T21:00:00",
            end_time="2026-07-23T22:00:00",
            launch_location={"type": "Feature", "geometry": None, "properties": {"label": "Campus waterfront"}},
            operational_area={"type": "Feature", "geometry": None, "properties": {"label": "Corpus Christi Bay"}},
            maximum_altitude_agl_ft=300,
            maximum_distance_from_pilot_m=600,
            operation_over_people=False,
            operation_over_moving_vehicles=False,
            visual_line_of_sight=True,
            night_operation=True,
            expected_people_count=0,
            controlled_ground_area=True,
            notes="Baseline mission",
        ),
    )
    yield settings, session, user, mission
    session.close()
    database.dispose()


def test_mocked_knowledge_agent_response_drives_needs_review(service_context):
    settings, session, user, mission = service_context
    decision, _ = EvaluationService(
        session,
        settings,
        ControlledAirspaceKnowledgeClient(),
        MockLLMProvider(),
    ).evaluate(
        user=user,
        mission_id=mission.mission_id,
        payload=MissionEvaluationRequest(grid_cells=[]),
    )

    assert decision.decision == "NEEDS_REVIEW"


def test_mocked_llm_structured_output_updates_mission(service_context):
    settings, session, user, mission = service_context
    response = ChatService(session, DeterministicExtractionLLM()).chat(
        user=user,
        mission_id=mission.mission_id,
        message="Update the altitude and VLOS flags.",
    )

    assert response.mission.maximum_altitude_agl_ft == 280
    assert response.mission.visual_line_of_sight is True


def test_mock_llm_extraction_handles_vlos_negation_and_time_phrasing(service_context):
    _settings, _session, _user, mission = service_context
    extraction = MockLLMProvider().extract_mission_update(
        message=(
            "Tomorrow at 9 pm we will fly at 280 feet near the TAMU-CC waterfront, "
            "stay within visual line of sight, not over people, and not over moving vehicles."
        ),
        mission=mission,
    )

    assert extraction.updates.maximum_altitude_agl_ft == 280
    assert extraction.updates.night_operation is True
    assert extraction.updates.visual_line_of_sight is True
    assert extraction.updates.operation_over_people is False
    assert extraction.updates.operation_over_moving_vehicles is False
    assert extraction.updates.launch_location is not None
    assert "TAMU-CC waterfront" in extraction.updates.launch_location["properties"]["label"]


def test_knowledge_agent_timeout_gracefully_needs_review(service_context):
    settings, session, user, mission = service_context
    decision, _ = EvaluationService(
        session,
        settings,
        TimeoutKnowledgeClient(),
        MockLLMProvider(),
    ).evaluate(
        user=user,
        mission_id=mission.mission_id,
        payload=MissionEvaluationRequest(grid_cells=[]),
    )

    assert decision.decision == "NEEDS_REVIEW"
    assert "could not be fully verified" in decision.concise_summary


def test_invalid_knowledge_agent_response_falls_back_to_safe_review_state(service_context):
    settings, session, user, mission = service_context
    decision, simulator_package = EvaluationService(
        session,
        settings,
        InvalidKnowledgeClient(),
        MockLLMProvider(),
    ).evaluate(
        user=user,
        mission_id=mission.mission_id,
        payload=MissionEvaluationRequest(grid_cells=[]),
    )

    assert decision.decision == "NEEDS_REVIEW"
    assert "could not be validated" in decision.concise_summary
    assert simulator_package is None


def test_unsupported_explanation_claim_falls_back_to_deterministic_summary(service_context):
    settings, session, user, mission = service_context
    decision, _ = EvaluationService(
        session,
        settings,
        ControlledAirspaceKnowledgeClient(),
        UnsupportedExplanationLLM(),
    ).evaluate(
        user=user,
        mission_id=mission.mission_id,
        payload=MissionEvaluationRequest(grid_cells=[]),
    )

    assert decision.narrative_explanation == decision.concise_summary

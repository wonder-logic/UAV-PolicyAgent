from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from policy_agent.api.schemas import PolicyChatEvaluationStage, PolicyKnowledgeSource
from policy_agent.config import Settings
from policy_agent.core.exceptions import ExternalServiceError
from policy_agent.integrations.knowledge_agent_client import BaseKnowledgeAgentClient
from policy_agent.integrations.llm_provider import BaseLLMProvider
from policy_agent.policies import DeterministicPolicyEngine
from policy_agent.policies.verification import explanation_is_supported, validate_citations
from policy_agent.schemas.common import DecisionStatus, VerificationStatus
from policy_agent.schemas.knowledge import KnowledgeAgentRequest, KnowledgeAgentResponse
from policy_agent.schemas.mission import MissionDecision, MissionDetailsRead, SimulatorPolicyPackage
from policy_agent.utils.datetime_utils import utcnow


@dataclass(slots=True)
class SharedMissionEvaluationResult:
    evaluation_stage: PolicyChatEvaluationStage
    knowledge_agent_called: bool
    knowledge_source: PolicyKnowledgeSource
    knowledge_request: KnowledgeAgentRequest | None
    knowledge_response: KnowledgeAgentResponse | None
    knowledge_response_payload: dict[str, Any] | None
    decision: MissionDecision
    simulator_package: SimulatorPolicyPackage | None
    errors: list[str]


def build_knowledge_request(
    *,
    mission: MissionDetailsRead,
    grid_cells: list[dict[str, object]],
    drone,
) -> KnowledgeAgentRequest:
    return KnowledgeAgentRequest(
        request_id=f"kar-{mission.mission_id}",
        mission_id=mission.mission_id,
        location=mission.launch_location,
        operational_area=mission.operational_area,
        mission_time_start=mission.start_time,
        mission_time_end=mission.end_time,
        altitude_ft=mission.maximum_altitude_agl_ft,
        drone_characteristics={
            "manufacturer": getattr(drone, "manufacturer", None),
            "model": getattr(drone, "model", None),
            "weight_grams": getattr(drone, "weight_grams", None),
            "remote_id_type": getattr(drone, "remote_id_type", None),
        },
        requested_context_categories=[
            "airspace_class",
            "controlled_airspace",
            "authorization_requirements",
            "temporary_flight_restrictions",
            "airport_proximity",
            "weather",
            "geographic_restrictions",
            "ground_features",
            "people_density",
            "restricted_areas",
            "grid_cell_facts",
        ],
        grid_cells=grid_cells,
    )


def _provisional_decision(
    *,
    mission: MissionDetailsRead,
    policy_version: str,
    summary: str,
    missing_information: list[str],
    review_reasons: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    required_actions: list[str] | None = None,
) -> MissionDecision:
    return MissionDecision(
        mission_id=mission.mission_id,
        decision=DecisionStatus.NEEDS_REVIEW,
        concise_summary=summary,
        narrative_explanation=summary,
        policy_evaluations=[],
        blocking_reasons=blocking_reasons or [],
        review_reasons=review_reasons or [],
        missing_information=missing_information,
        required_actions=required_actions or [],
        citations=[],
        evaluation_timestamp=utcnow(),
        policy_version=policy_version,
    )


def _knowledge_source_from_response(response: KnowledgeAgentResponse | None) -> PolicyKnowledgeSource:
    if response is None:
        return PolicyKnowledgeSource.NONE
    source = (response.source or "").casefold()
    if "mock" in source:
        return PolicyKnowledgeSource.MOCK
    return PolicyKnowledgeSource.KNOWLEDGE_AGENT


def _point_feature(*, label: str | None) -> dict[str, Any] | None:
    if not label:
        return None
    return {
        "type": "Feature",
        "geometry": None,
        "properties": {"label": label},
    }


def _route_feature(*, start_label: str | None, destination_label: str | None) -> dict[str, Any] | None:
    if not start_label and not destination_label:
        return None
    return {
        "type": "Feature",
        "geometry": None,
        "properties": {"label": f"{start_label or 'Launch point'} to {destination_label or 'Destination'}"},
    }


class SharedMissionEvaluator:
    def __init__(
        self,
        *,
        settings: Settings,
        knowledge_client: BaseKnowledgeAgentClient,
        llm_provider: BaseLLMProvider,
    ):
        self.settings = settings
        self.knowledge_client = knowledge_client
        self.llm_provider = llm_provider
        self.engine = DeterministicPolicyEngine(policy_version=settings.policy_version)

    def evaluate(
        self,
        *,
        mission: MissionDetailsRead,
        profile,
        drone,
        missing_fields: list[str],
        grid_cells: list[dict[str, object]],
        knowledge_request: KnowledgeAgentRequest | None = None,
        knowledge_response_override: KnowledgeAgentResponse | None = None,
        knowledge_response_payload: dict[str, Any] | None = None,
        knowledge_source_override: PolicyKnowledgeSource | None = None,
    ) -> SharedMissionEvaluationResult:
        resolved_knowledge_request = knowledge_request or build_knowledge_request(
            mission=mission,
            grid_cells=grid_cells,
            drone=drone,
        )

        if missing_fields:
            summary = "I still need a few mission details before I can run the grounded Knowledge Agent review."
            decision = _provisional_decision(
                mission=mission,
                policy_version=self.settings.policy_version,
                summary=summary,
                missing_information=list(missing_fields),
                review_reasons=["Required mission details are still missing."],
                required_actions=["Answer the next follow-up question so the grounded evaluation can continue."],
            )
            return SharedMissionEvaluationResult(
                evaluation_stage=PolicyChatEvaluationStage.PRELIMINARY,
                knowledge_agent_called=False,
                knowledge_source=PolicyKnowledgeSource.NONE,
                knowledge_request=resolved_knowledge_request,
                knowledge_response=None,
                knowledge_response_payload=None,
                decision=decision,
                simulator_package=None,
                errors=[],
            )

        resolved_knowledge_response: KnowledgeAgentResponse | None = None
        resolved_knowledge_payload = knowledge_response_payload
        knowledge_agent_called = False
        knowledge_source = knowledge_source_override or PolicyKnowledgeSource.NONE

        if knowledge_response_override is not None:
            resolved_knowledge_response = knowledge_response_override
            resolved_knowledge_payload = resolved_knowledge_payload or knowledge_response_override.model_dump(mode="json")
            knowledge_source = knowledge_source_override or PolicyKnowledgeSource.SUPPLIED
        else:
            knowledge_agent_called = True
            try:
                raw_knowledge_response = self.knowledge_client.fetch_facts(resolved_knowledge_request)
            except ExternalServiceError as exc:
                decision = _provisional_decision(
                    mission=mission,
                    policy_version=self.settings.policy_version,
                    summary="The Knowledge Agent could not be reached, so the mission could not be fully verified.",
                    missing_information=["knowledge_agent_facts"],
                    review_reasons=["Verified airspace and geographic facts are temporarily unavailable."],
                    required_actions=["Retry the grounded review when the Knowledge Agent is available."],
                )
                return SharedMissionEvaluationResult(
                    evaluation_stage=PolicyChatEvaluationStage.KNOWLEDGE_PENDING,
                    knowledge_agent_called=True,
                    knowledge_source=PolicyKnowledgeSource.NONE,
                    knowledge_request=resolved_knowledge_request,
                    knowledge_response=None,
                    knowledge_response_payload=None,
                    decision=decision,
                    simulator_package=None,
                    errors=[str(exc)],
                )
            except Exception as exc:
                decision = _provisional_decision(
                    mission=mission,
                    policy_version=self.settings.policy_version,
                    summary="The grounded review stopped because the Knowledge Agent integration returned an unexpected error.",
                    missing_information=["knowledge_agent_facts"],
                    review_reasons=["The Knowledge Agent integration failed before facts could be validated."],
                    required_actions=["Retry the grounded review after checking the Knowledge Agent integration."],
                )
                return SharedMissionEvaluationResult(
                    evaluation_stage=PolicyChatEvaluationStage.ERROR,
                    knowledge_agent_called=True,
                    knowledge_source=PolicyKnowledgeSource.NONE,
                    knowledge_request=resolved_knowledge_request,
                    knowledge_response=None,
                    knowledge_response_payload=None,
                    decision=decision,
                    simulator_package=None,
                    errors=[str(exc)],
                )

            if isinstance(raw_knowledge_response, KnowledgeAgentResponse):
                resolved_knowledge_payload = raw_knowledge_response.model_dump(mode="json")
            elif isinstance(raw_knowledge_response, dict):
                resolved_knowledge_payload = raw_knowledge_response
            else:
                resolved_knowledge_payload = {"raw_response": str(raw_knowledge_response)}

            try:
                resolved_knowledge_response = KnowledgeAgentResponse.model_validate(raw_knowledge_response)
            except Exception as exc:
                decision = _provisional_decision(
                    mission=mission,
                    policy_version=self.settings.policy_version,
                    summary="The Knowledge Agent response could not be validated, so I cannot treat the result as a final compliance decision.",
                    missing_information=["knowledge_agent_facts"],
                    review_reasons=["The Knowledge Agent response schema was invalid."],
                    required_actions=["Retry the grounded review after correcting the Knowledge Agent response."],
                )
                return SharedMissionEvaluationResult(
                    evaluation_stage=PolicyChatEvaluationStage.ERROR,
                    knowledge_agent_called=True,
                    knowledge_source=PolicyKnowledgeSource.NONE,
                    knowledge_request=resolved_knowledge_request,
                    knowledge_response=None,
                    knowledge_response_payload=resolved_knowledge_payload,
                    decision=decision,
                    simulator_package=None,
                    errors=[f"Knowledge Agent response validation failed: {exc}"],
                )

            knowledge_source = _knowledge_source_from_response(resolved_knowledge_response)

        assert resolved_knowledge_response is not None
        if resolved_knowledge_response.mission_id != mission.mission_id:
            decision = _provisional_decision(
                mission=mission,
                policy_version=self.settings.policy_version,
                summary="The Knowledge Agent returned facts for a different mission identifier, so I cannot use them as a final answer.",
                missing_information=["knowledge_agent_mission_id"],
                review_reasons=["The Knowledge Agent mission identifier did not match the current mission."],
                required_actions=["Retry the grounded review with a matching Knowledge Agent mission identifier."],
            )
            return SharedMissionEvaluationResult(
                evaluation_stage=PolicyChatEvaluationStage.ERROR,
                knowledge_agent_called=knowledge_agent_called,
                knowledge_source=knowledge_source,
                knowledge_request=resolved_knowledge_request,
                knowledge_response=resolved_knowledge_response,
                knowledge_response_payload=resolved_knowledge_payload,
                decision=decision,
                simulator_package=None,
                errors=["Knowledge Agent mission_id did not match the mission under evaluation."],
            )

        decision = self.engine.evaluate(
            mission=mission,
            profile=profile,
            drone=drone,
            knowledge_response=resolved_knowledge_response,
        )
        citation_errors = validate_citations(decision.citations)
        if citation_errors:
            error_decision = _provisional_decision(
                mission=mission,
                policy_version=self.settings.policy_version,
                summary="The grounded review found citation validation issues, so I cannot present it as a final decision.",
                missing_information=["trusted_citation_validation"],
                review_reasons=["One or more policy citations failed trusted validation."],
                required_actions=["Correct the policy citation bundle before relying on this review."],
            )
            return SharedMissionEvaluationResult(
                evaluation_stage=PolicyChatEvaluationStage.ERROR,
                knowledge_agent_called=knowledge_agent_called,
                knowledge_source=knowledge_source,
                knowledge_request=resolved_knowledge_request,
                knowledge_response=resolved_knowledge_response,
                knowledge_response_payload=resolved_knowledge_payload,
                decision=error_decision,
                simulator_package=None,
                errors=citation_errors,
            )

        simulator_package = self.engine.build_simulator_package(
            mission=mission,
            profile=profile,
            drone=drone,
            knowledge_response=resolved_knowledge_response,
            overall_decision=decision,
        )
        explanation = self.llm_provider.generate_decision_explanation(mission=mission, decision=decision)
        if not explanation_is_supported(explanation=explanation, citations=decision.citations):
            explanation = decision.concise_summary
        decision.narrative_explanation = explanation

        return SharedMissionEvaluationResult(
            evaluation_stage=PolicyChatEvaluationStage.FINAL,
            knowledge_agent_called=knowledge_agent_called,
            knowledge_source=knowledge_source,
            knowledge_request=resolved_knowledge_request,
            knowledge_response=resolved_knowledge_response,
            knowledge_response_payload=resolved_knowledge_payload,
            decision=decision,
            simulator_package=simulator_package,
            errors=[],
        )


def build_chat_profile(*, mission, policy_request):
    from policy_agent.db.models import UserPolicyProfile

    profile = UserPolicyProfile(
        full_name="Chat Operator",
        email="chat@example.com",
        jurisdiction="US",
        operator_type=(policy_request.operation_type or "unknown").replace("_", " "),
        preferred_units="imperial",
    )
    profile.credentials = []

    if policy_request.pilot_certification_provided is True:
        profile.remote_pilot_certificate_number = "CHAT-PART107"
        profile.remote_pilot_certificate_issue_date = mission.created_at.date()
        profile.remote_pilot_certificate_expiration = mission.created_at.date() + timedelta(days=365)
        # Chat flow records a single operator-readiness flag rather than separate training records.
        profile.recurrent_training_completed = True
        profile.recurrent_training_date = mission.created_at.date()
    else:
        profile.remote_pilot_certificate_number = None
        profile.remote_pilot_certificate_issue_date = None
        profile.remote_pilot_certificate_expiration = None
        profile.recurrent_training_completed = False
        profile.recurrent_training_date = None

    if policy_request.controlled_airspace_authorization_provided is True:
        from policy_agent.db.models import ProfileCredential

        authorization = ProfileCredential(
            credential_kind="authorization",
            credential_type="LAANC airspace authorization",
            issuing_authority="FAA",
            verification_status=VerificationStatus.VERIFIED.value,
            restrictions=[],
            source="chat",
        )
        profile.credentials.append(authorization)

    return profile


def build_chat_drone(*, mission, policy_request):
    from policy_agent.db.models import DroneProfile

    drone = DroneProfile(
        owner_user_id=mission.user_id,
        nickname="Chat mission aircraft",
        manufacturer=policy_request.drone_manufacturer or "Unknown",
        model=policy_request.drone_model or "Unknown",
        weight_grams=policy_request.drone_weight_grams,
        maximum_takeoff_weight_grams=policy_request.max_takeoff_weight_grams,
        remote_id_type="standard" if policy_request.remote_id_available is True else None,
        remote_id_serial_number="CHAT-RID" if policy_request.remote_id_available is True else None,
        anti_collision_lighting=policy_request.anti_collision_lights,
        light_visibility_statute_miles=3.0 if policy_request.anti_collision_lights is True else None,
        maximum_endurance_minutes=(
            int(policy_request.endurance_minutes) if policy_request.endurance_minutes is not None else None
        ),
        maximum_operating_altitude_ft=(
            int(policy_request.altitude_ft) if policy_request.altitude_ft is not None else None
        ),
        verification_status=VerificationStatus.VERIFIED.value,
        is_default=True,
    )
    return drone


def build_chat_mission(*, mission_id: str, policy_request):
    timestamp = utcnow()
    origin_label = policy_request.origin_location or policy_request.live_location
    destination_label = policy_request.destination_location
    purpose = policy_request.mission_purpose or (
        f"{policy_request.operation_type.replace('_', ' ').title()} mission"
        if policy_request.operation_type and policy_request.operation_type != "unknown"
        else "Mission under review"
    )
    return MissionDetailsRead(
        mission_id=mission_id,
        user_id="chat-user",
        drone_id=policy_request.drone_model_id or "chat-drone",
        purpose=purpose,
        start_time=None,
        end_time=None,
        launch_location=_point_feature(label=origin_label),
        operational_area=_route_feature(start_label=origin_label, destination_label=destination_label),
        maximum_altitude_agl_ft=policy_request.altitude_ft,
        maximum_distance_from_pilot_m=None,
        operation_over_people=policy_request.over_people,
        operation_over_moving_vehicles=policy_request.over_moving_vehicles,
        visual_line_of_sight=policy_request.visual_line_of_sight,
        night_operation=policy_request.night_operation,
        expected_people_count=None,
        controlled_ground_area=policy_request.local_restrictions_known,
        notes=policy_request.additional_context,
        status="collecting_information",
        latest_decision=None,
        evaluation_timestamp=None,
        created_at=timestamp,
        updated_at=timestamp,
    )

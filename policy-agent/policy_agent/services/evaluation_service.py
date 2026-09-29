from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from policy_agent.config import Settings
from policy_agent.core.exceptions import NotFoundError, ValidationError
from policy_agent.db.models import Mission, UserAccount
from policy_agent.integrations import BaseKnowledgeAgentClient, BaseLLMProvider
from policy_agent.repositories import DroneRepository, MissionRepository, ProfileRepository
from policy_agent.schemas.mission import (
    MissionDecision,
    MissionEvaluationRequest,
    SimulatorPolicyPackage,
)
from policy_agent.services.mappers import mission_to_schema
from policy_agent.services.mission_service import collect_missing_mission_fields
from policy_agent.services.mission_evaluator import SharedMissionEvaluator
from policy_agent.utils.datetime_utils import utcnow


def _build_idempotency_key(mission: Mission, grid_cells: list[dict[str, object]]) -> str:
    payload = {
        "mission_id": mission.id,
        "updated_at": mission.updated_at.isoformat(),
        "grid_cells": grid_cells,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


class EvaluationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        knowledge_client: BaseKnowledgeAgentClient,
        llm_provider: BaseLLMProvider,
    ):
        self.session = session
        self.settings = settings
        self.knowledge_client = knowledge_client
        self.llm_provider = llm_provider
        self.missions = MissionRepository(session)
        self.profiles = ProfileRepository(session)
        self.drones = DroneRepository(session)
        self.shared_evaluator = SharedMissionEvaluator(
            settings=settings,
            knowledge_client=knowledge_client,
            llm_provider=llm_provider,
        )

    def _load_context(self, user: UserAccount, mission_id: str):
        mission = self.missions.get_for_user(user.id, mission_id)
        if mission is None:
            raise NotFoundError("Mission not found.")
        profile = self.profiles.get_profile(user.id)
        drone = self.drones.get_for_user(user.id, mission.drone_id)
        if drone is None:
            raise ValidationError("Select a valid drone before evaluating the mission.")
        return mission, profile, drone

    def evaluate(
        self,
        *,
        user: UserAccount,
        mission_id: str,
        payload: MissionEvaluationRequest,
    ) -> tuple[MissionDecision, SimulatorPolicyPackage | None]:
        mission, profile, drone = self._load_context(user, mission_id)
        missing_fields = collect_missing_mission_fields(mission=mission, profile=profile, drone=drone)
        idempotency_key = payload.idempotency_key or _build_idempotency_key(mission, payload.grid_cells)
        cached = self.missions.get_evaluation(mission.id, idempotency_key)
        if cached and cached.decision_payload:
            return (
                MissionDecision.model_validate(cached.decision_payload),
                SimulatorPolicyPackage.model_validate(cached.simulator_package_payload)
                if cached.simulator_package_payload
                else None,
            )

        evaluation = cached or self.missions.create_evaluation(
            mission_id=mission.id,
            idempotency_key=idempotency_key,
            state="waiting_for_knowledge_agent",
        )
        mission_schema = mission_to_schema(mission)
        shared_result = self.shared_evaluator.evaluate(
            mission=mission_schema,
            profile=profile,
            drone=drone,
            missing_fields=missing_fields,
            grid_cells=payload.grid_cells,
        )
        decision = shared_result.decision
        simulator_package = shared_result.simulator_package
        mission.latest_decision = decision.decision
        mission.evaluation_timestamp = decision.evaluation_timestamp
        mission.status = (
            "completed"
            if shared_result.evaluation_stage == "FINAL"
            else "collecting_information"
            if shared_result.evaluation_stage == "PRELIMINARY"
            else "failed"
        )
        self.missions.update_evaluation(
            evaluation,
            state=mission.status,
            knowledge_request_payload=(
                shared_result.knowledge_request.model_dump(mode="json") if shared_result.knowledge_request else None
            ),
            knowledge_response_payload=shared_result.knowledge_response_payload,
            policy_evaluations_payload=[item.model_dump(mode="json") for item in decision.policy_evaluations],
            decision_payload=decision.model_dump(mode="json"),
            simulator_package_payload=simulator_package.model_dump(mode="json") if simulator_package else None,
            explanation_payload={"explanation": decision.narrative_explanation},
            error_message="; ".join(shared_result.errors) if shared_result.errors else None,
            completed_at=utcnow(),
        )
        self.session.add(mission)
        self.session.commit()
        return decision, simulator_package

    def get_latest_decision(self, *, user: UserAccount, mission_id: str) -> MissionDecision:
        mission, _, _ = self._load_context(user, mission_id)
        latest = self.missions.get_latest_evaluation(mission.id)
        if latest is None or latest.decision_payload is None:
            raise NotFoundError("No decision is available for this mission yet.")
        return MissionDecision.model_validate(latest.decision_payload)

    def get_latest_simulator_package(self, *, user: UserAccount, mission_id: str) -> SimulatorPolicyPackage:
        mission, _, _ = self._load_context(user, mission_id)
        latest = self.missions.get_latest_evaluation(mission.id)
        if latest is None or latest.simulator_package_payload is None:
            raise NotFoundError("No simulator package is available for this mission yet.")
        return SimulatorPolicyPackage.model_validate(latest.simulator_package_payload)

from __future__ import annotations

from sqlalchemy.orm import Session

from policy_agent.core.exceptions import NotFoundError
from policy_agent.db.models import Mission, UserAccount
from policy_agent.integrations.llm_provider import BaseLLMProvider
from policy_agent.repositories import DroneRepository, MissionRepository, ProfileRepository
from policy_agent.schemas.chat import MissionChatResponse
from policy_agent.schemas.mission import MissionDecision, MissionUpdate, MissionUpdateExtraction
from policy_agent.services.mappers import conversation_to_schema, mission_to_schema
from policy_agent.services.mission_service import collect_missing_mission_fields


def merge_mission_updates(*, mission: Mission, updates: MissionUpdate) -> Mission:
    payload = updates.model_dump(exclude_none=True)
    for field_name, value in payload.items():
        setattr(mission, field_name, value)
    return mission


class ChatService:
    def __init__(self, session: Session, llm_provider: BaseLLMProvider):
        self.session = session
        self.llm_provider = llm_provider
        self.missions = MissionRepository(session)
        self.profiles = ProfileRepository(session)
        self.drones = DroneRepository(session)

    def _build_assistant_message(
        self,
        *,
        extraction: MissionUpdateExtraction,
        missing_fields: list[str],
        decision_preview: MissionDecision | None,
    ) -> str:
        if decision_preview is not None and not missing_fields:
            return decision_preview.narrative_explanation or decision_preview.concise_summary
        if missing_fields:
            why = extraction.follow_up_question or "I still need one more mission detail before evaluation."
            if extraction.uncertain_fields:
                return (
                    "I updated the mission with the details I could verify from your message. "
                    f"Some items still need confirmation. {why}"
                )
            return f"I updated the mission details. {why}"
        return "I updated the mission details and you have enough information to run a deterministic policy evaluation."

    def chat(
        self,
        *,
        user: UserAccount,
        mission_id: str,
        message: str,
        decision_preview: MissionDecision | None = None,
    ) -> MissionChatResponse:
        mission = self.missions.get_for_user(user.id, mission_id)
        if mission is None:
            raise NotFoundError("Mission not found.")

        mission_schema = mission_to_schema(mission)
        extraction = self.llm_provider.extract_mission_update(message=message, mission=mission_schema)
        merge_mission_updates(mission=mission, updates=extraction.updates)

        profile = self.profiles.get_profile(user.id)
        drone = self.drones.get_for_user(user.id, mission.drone_id)
        missing_fields = collect_missing_mission_fields(mission=mission, profile=profile, drone=drone)
        mission.status = "ready_for_knowledge_agent" if not missing_fields else "collecting_information"

        self.missions.create_conversation_message(
            mission_id=mission.id,
            role="user",
            content=message,
            structured_update=extraction.updates.model_dump(mode="json", exclude_none=True),
        )
        assistant_message = self._build_assistant_message(
            extraction=extraction,
            missing_fields=missing_fields,
            decision_preview=decision_preview,
        )
        self.missions.create_conversation_message(
            mission_id=mission.id,
            role="assistant",
            content=assistant_message,
            structured_update={"missing_fields": missing_fields},
        )

        self.session.add(mission)
        self.session.commit()

        refreshed = self.missions.get_for_user(user.id, mission_id)
        assert refreshed is not None
        conversation = [conversation_to_schema(item) for item in self.missions.list_conversation(refreshed.id)]

        return MissionChatResponse(
            mission=mission_to_schema(refreshed),
            assistant_message=assistant_message,
            extraction=extraction,
            missing_fields=missing_fields,
            next_required_action=extraction.follow_up_question,
            decision_preview=decision_preview,
            conversation=conversation,
        )

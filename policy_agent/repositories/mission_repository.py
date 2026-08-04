from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from policy_agent.db.models import Mission, MissionConversationMessage, MissionEvaluation


class MissionRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_user(self, user_id: str) -> list[Mission]:
        statement = select(Mission).where(Mission.user_id == user_id).order_by(Mission.updated_at.desc())
        return list(self.session.scalars(statement))

    def get_for_user(self, user_id: str, mission_id: str) -> Mission | None:
        statement = (
            select(Mission)
            .options(
                selectinload(Mission.conversations),
                selectinload(Mission.evaluations),
                selectinload(Mission.drone),
            )
            .where(Mission.user_id == user_id, Mission.id == mission_id)
        )
        return self.session.scalar(statement)

    def create(self, **payload) -> Mission:
        mission = Mission(**payload)
        self.session.add(mission)
        self.session.flush()
        return mission

    def update(self, mission: Mission, **payload) -> Mission:
        for key, value in payload.items():
            setattr(mission, key, value)
        self.session.add(mission)
        self.session.flush()
        return mission

    def create_conversation_message(
        self,
        *,
        mission_id: str,
        role: str,
        content: str,
        structured_update: dict | None = None,
    ) -> MissionConversationMessage:
        message = MissionConversationMessage(
            mission_id=mission_id,
            role=role,
            content=content,
            structured_update=structured_update,
        )
        self.session.add(message)
        self.session.flush()
        return message

    def list_conversation(self, mission_id: str) -> list[MissionConversationMessage]:
        statement = (
            select(MissionConversationMessage)
            .where(MissionConversationMessage.mission_id == mission_id)
            .order_by(MissionConversationMessage.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def get_evaluation(self, mission_id: str, idempotency_key: str) -> MissionEvaluation | None:
        statement = select(MissionEvaluation).where(
            MissionEvaluation.mission_id == mission_id,
            MissionEvaluation.idempotency_key == idempotency_key,
        )
        return self.session.scalar(statement)

    def create_evaluation(self, **payload) -> MissionEvaluation:
        evaluation = MissionEvaluation(**payload)
        self.session.add(evaluation)
        self.session.flush()
        return evaluation

    def get_latest_evaluation(self, mission_id: str) -> MissionEvaluation | None:
        statement = (
            select(MissionEvaluation)
            .where(MissionEvaluation.mission_id == mission_id)
            .order_by(MissionEvaluation.updated_at.desc())
        )
        return self.session.scalar(statement)

    def update_evaluation(self, evaluation: MissionEvaluation, **payload) -> MissionEvaluation:
        for key, value in payload.items():
            setattr(evaluation, key, value)
        self.session.add(evaluation)
        self.session.flush()
        return evaluation

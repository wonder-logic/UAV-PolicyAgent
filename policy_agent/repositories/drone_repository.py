from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from policy_agent.db.models import DroneProfile


class DroneRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_user(self, user_id: str) -> list[DroneProfile]:
        statement = (
            select(DroneProfile)
            .where(DroneProfile.owner_user_id == user_id)
            .order_by(DroneProfile.is_default.desc(), DroneProfile.updated_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_for_user(self, user_id: str, drone_id: str) -> DroneProfile | None:
        statement = select(DroneProfile).where(
            DroneProfile.owner_user_id == user_id,
            DroneProfile.id == drone_id,
        )
        return self.session.scalar(statement)

    def clear_default_for_user(self, user_id: str) -> None:
        self.session.execute(update(DroneProfile).where(DroneProfile.owner_user_id == user_id).values(is_default=False))

    def create(self, **payload) -> DroneProfile:
        drone = DroneProfile(**payload)
        self.session.add(drone)
        self.session.flush()
        return drone

    def update(self, drone: DroneProfile, **payload) -> DroneProfile:
        for key, value in payload.items():
            setattr(drone, key, value)
        self.session.add(drone)
        self.session.flush()
        return drone

    def delete(self, drone: DroneProfile) -> None:
        self.session.delete(drone)
        self.session.flush()

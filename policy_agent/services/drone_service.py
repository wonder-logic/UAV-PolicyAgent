from __future__ import annotations

from sqlalchemy.orm import Session

from policy_agent.core.exceptions import NotFoundError
from policy_agent.db.models import UserAccount
from policy_agent.repositories import DroneRepository
from policy_agent.schemas.drone import DroneProfileCreate, DroneProfileRead, DroneProfileUpdate
from policy_agent.services.mappers import drone_to_schema


class DroneService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = DroneRepository(session)

    def create_drone(self, user: UserAccount, payload: DroneProfileCreate) -> DroneProfileRead:
        existing = self.repository.list_for_user(user.id)
        if payload.is_default or not existing:
            self.repository.clear_default_for_user(user.id)
        drone = self.repository.create(owner_user_id=user.id, **payload.model_dump())
        self.session.commit()
        return drone_to_schema(drone)

    def list_drones(self, user: UserAccount) -> list[DroneProfileRead]:
        return [drone_to_schema(drone) for drone in self.repository.list_for_user(user.id)]

    def get_drone(self, user: UserAccount, drone_id: str) -> DroneProfileRead:
        drone = self.repository.get_for_user(user.id, drone_id)
        if drone is None:
            raise NotFoundError("Drone profile not found.")
        return drone_to_schema(drone)

    def update_drone(self, user: UserAccount, drone_id: str, payload: DroneProfileUpdate) -> DroneProfileRead:
        drone = self.repository.get_for_user(user.id, drone_id)
        if drone is None:
            raise NotFoundError("Drone profile not found.")

        update_data = payload.model_dump(exclude_none=True)
        if update_data.get("is_default") is True:
            self.repository.clear_default_for_user(user.id)
        updated = self.repository.update(drone, **update_data)
        self.session.commit()
        return drone_to_schema(updated)

    def delete_drone(self, user: UserAccount, drone_id: str) -> None:
        drone = self.repository.get_for_user(user.id, drone_id)
        if drone is None:
            raise NotFoundError("Drone profile not found.")

        self.repository.delete(drone)
        self.session.commit()

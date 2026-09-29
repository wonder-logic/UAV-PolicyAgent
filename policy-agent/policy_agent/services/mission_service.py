from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from policy_agent.core.exceptions import NotFoundError, ValidationError
from policy_agent.db.models import UserAccount
from policy_agent.repositories import DroneRepository, MissionRepository, ProfileRepository
from policy_agent.schemas.mission import (
    MissionCreate,
    MissionDetailsRead,
    MissionHistoryItem,
    MissionUpdateRequest,
)
from policy_agent.services.mappers import mission_history_to_schema, mission_to_schema
from policy_agent.services.profile_utils import profile_is_certificate_current


@dataclass(slots=True)
class MissionReadiness:
    missing_fields: list[str]
    ready_for_evaluation: bool


def collect_missing_mission_fields(*, mission, profile, drone) -> list[str]:
    missing: list[str] = []

    if mission.start_time is None:
        missing.append("start_time")
    if mission.launch_location is None:
        missing.append("launch_location")
    if mission.operational_area is None:
        missing.append("operational_area")
    if mission.maximum_altitude_agl_ft is None:
        missing.append("maximum_altitude_agl_ft")
    if mission.visual_line_of_sight is None:
        missing.append("visual_line_of_sight")
    if mission.night_operation is None:
        missing.append("night_operation")
    if mission.operation_over_people is None:
        missing.append("operation_over_people")
    if mission.operation_over_moving_vehicles is None:
        missing.append("operation_over_moving_vehicles")

    if profile is None:
        missing.extend(["profile", "pilot_certification"])
    else:
        if not profile.remote_pilot_certificate_number:
            missing.append("pilot_certification")
        elif not profile_is_certificate_current(profile):
            missing.append("pilot_certification_validity")

    if drone is None:
        missing.extend(["drone", "remote_id"])
    else:
        if not drone.remote_id_type and not drone.remote_id_serial_number:
            missing.append("remote_id")

    return missing


class MissionService:
    def __init__(self, session: Session):
        self.session = session
        self.missions = MissionRepository(session)
        self.drones = DroneRepository(session)
        self.profiles = ProfileRepository(session)

    def create_mission(self, user: UserAccount, payload: MissionCreate) -> MissionDetailsRead:
        drone = self.drones.get_for_user(user.id, payload.drone_id)
        if drone is None:
            raise NotFoundError("Select a drone from your account before creating the mission.")

        mission = self.missions.create(user_id=user.id, status="draft", **payload.model_dump())
        self.session.commit()
        return mission_to_schema(mission)

    def list_missions(self, user: UserAccount) -> list[MissionHistoryItem]:
        return [mission_history_to_schema(item) for item in self.missions.list_for_user(user.id)]

    def get_mission(self, user: UserAccount, mission_id: str) -> MissionDetailsRead:
        mission = self.missions.get_for_user(user.id, mission_id)
        if mission is None:
            raise NotFoundError("Mission not found.")
        return mission_to_schema(mission)

    def get_mission_record(self, user: UserAccount, mission_id: str):
        mission = self.missions.get_for_user(user.id, mission_id)
        if mission is None:
            raise NotFoundError("Mission not found.")
        return mission

    def update_mission(
        self,
        user: UserAccount,
        mission_id: str,
        payload: MissionUpdateRequest,
    ) -> MissionDetailsRead:
        mission = self.get_mission_record(user, mission_id)
        update_data = payload.model_dump(exclude_none=True)
        if "drone_id" in update_data:
            drone = self.drones.get_for_user(user.id, update_data["drone_id"])
            if drone is None:
                raise NotFoundError("Drone profile not found.")

        updated = self.missions.update(mission, **update_data)
        if updated.status == "completed":
            updated.status = "collecting_information"
        self.session.commit()
        return mission_to_schema(updated)

    def evaluate_readiness(self, user: UserAccount, mission_id: str) -> MissionReadiness:
        mission = self.get_mission_record(user, mission_id)
        profile = self.profiles.get_profile(user.id)
        drone = self.drones.get_for_user(user.id, mission.drone_id)
        missing = collect_missing_mission_fields(mission=mission, profile=profile, drone=drone)
        return MissionReadiness(missing_fields=missing, ready_for_evaluation=not missing)

    def submit_mission(self, user: UserAccount, mission_id: str) -> MissionDetailsRead:
        mission = self.get_mission_record(user, mission_id)
        readiness = self.evaluate_readiness(user, mission_id)
        mission.status = "ready_for_knowledge_agent" if readiness.ready_for_evaluation else "collecting_information"
        self.session.add(mission)
        self.session.commit()
        return mission_to_schema(mission)

    def require_latest_evaluation_payload(self, user: UserAccount, mission_id: str, payload_key: str) -> dict:
        mission = self.get_mission_record(user, mission_id)
        latest = self.missions.get_latest_evaluation(mission.id)
        if latest is None:
            raise NotFoundError("Evaluate the mission before requesting this artifact.")

        payload = getattr(latest, payload_key)
        if payload is None:
            raise ValidationError("The requested mission artifact is not available yet.")
        return payload

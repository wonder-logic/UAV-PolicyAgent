from __future__ import annotations

from typing import Iterable

from policy_agent.db.models import (
    DroneProfile,
    Mission,
    MissionConversationMessage,
    ProfileCredential,
    UserAccount,
    UserPolicyProfile,
)
from policy_agent.schemas.auth import SessionUser
from policy_agent.schemas.chat import ConversationMessage
from policy_agent.schemas.common import DecisionStatus, MissionWorkflowState, VerificationStatus
from policy_agent.schemas.drone import DroneProfileRead
from policy_agent.schemas.mission import MissionDetailsRead, MissionHistoryItem
from policy_agent.schemas.profile import CredentialRecordRead, UserPolicyProfileRead


def user_to_schema(user: UserAccount) -> SessionUser:
    return SessionUser(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        organization=user.organization,
        created_at=user.created_at,
    )


def credential_to_schema(credential: ProfileCredential) -> CredentialRecordRead:
    return CredentialRecordRead(
        credential_id=credential.id,
        credential_kind=credential.credential_kind,
        credential_type=credential.credential_type,
        identifier=credential.identifier,
        issuing_authority=credential.issuing_authority,
        issue_date=credential.issue_date,
        expiration_date=credential.expiration_date,
        verification_status=VerificationStatus(credential.verification_status),
        restrictions=list(credential.restrictions or []),
        uploaded_document_reference=credential.uploaded_document_reference,
        source=credential.source,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
    )


def _group_credentials(
    credentials: Iterable[ProfileCredential],
) -> tuple[list[CredentialRecordRead], list[CredentialRecordRead], list[CredentialRecordRead]]:
    certifications: list[CredentialRecordRead] = []
    authorizations: list[CredentialRecordRead] = []
    waivers: list[CredentialRecordRead] = []

    for credential in credentials:
        normalized_kind = credential.credential_kind.strip().lower()
        record = credential_to_schema(credential)
        if normalized_kind == "authorization":
            authorizations.append(record)
        elif normalized_kind == "waiver":
            waivers.append(record)
        else:
            certifications.append(record)

    return certifications, authorizations, waivers


def profile_to_schema(profile: UserPolicyProfile) -> UserPolicyProfileRead:
    certifications, authorizations, waivers = _group_credentials(profile.credentials)
    return UserPolicyProfileRead(
        user_id=profile.user_id,
        full_name=profile.full_name,
        email=profile.email,
        jurisdiction=profile.jurisdiction,
        operator_type=profile.operator_type,
        organization=profile.organization,
        preferred_units=profile.preferred_units,
        remote_pilot_certificate_number=profile.remote_pilot_certificate_number,
        remote_pilot_certificate_issue_date=profile.remote_pilot_certificate_issue_date,
        remote_pilot_certificate_expiration=profile.remote_pilot_certificate_expiration,
        recurrent_training_completed=profile.recurrent_training_completed,
        recurrent_training_date=profile.recurrent_training_date,
        waivers=waivers,
        authorizations=authorizations,
        certifications=certifications,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def drone_to_schema(drone: DroneProfile) -> DroneProfileRead:
    return DroneProfileRead(
        drone_id=drone.id,
        owner_user_id=drone.owner_user_id,
        nickname=drone.nickname,
        manufacturer=drone.manufacturer,
        model=drone.model,
        serial_number=drone.serial_number,
        registration_number=drone.registration_number,
        weight_grams=drone.weight_grams,
        maximum_takeoff_weight_grams=drone.maximum_takeoff_weight_grams,
        category=drone.category,
        remote_id_type=drone.remote_id_type,
        remote_id_serial_number=drone.remote_id_serial_number,
        anti_collision_lighting=drone.anti_collision_lighting,
        light_visibility_statute_miles=drone.light_visibility_statute_miles,
        maximum_endurance_minutes=drone.maximum_endurance_minutes,
        maximum_operating_altitude_ft=drone.maximum_operating_altitude_ft,
        verification_status=VerificationStatus(drone.verification_status),
        is_default=drone.is_default,
        created_at=drone.created_at,
        updated_at=drone.updated_at,
    )


def mission_to_schema(mission: Mission) -> MissionDetailsRead:
    return MissionDetailsRead(
        mission_id=mission.id,
        user_id=mission.user_id,
        drone_id=mission.drone_id,
        purpose=mission.purpose,
        start_time=mission.start_time,
        end_time=mission.end_time,
        launch_location=mission.launch_location,
        operational_area=mission.operational_area,
        maximum_altitude_agl_ft=mission.maximum_altitude_agl_ft,
        maximum_distance_from_pilot_m=mission.maximum_distance_from_pilot_m,
        operation_over_people=mission.operation_over_people,
        operation_over_moving_vehicles=mission.operation_over_moving_vehicles,
        visual_line_of_sight=mission.visual_line_of_sight,
        night_operation=mission.night_operation,
        expected_people_count=mission.expected_people_count,
        controlled_ground_area=mission.controlled_ground_area,
        notes=mission.notes,
        status=MissionWorkflowState(mission.status),
        latest_decision=DecisionStatus(mission.latest_decision) if mission.latest_decision else None,
        evaluation_timestamp=mission.evaluation_timestamp,
        created_at=mission.created_at,
        updated_at=mission.updated_at,
    )


def mission_history_to_schema(mission: Mission) -> MissionHistoryItem:
    location_summary = "Location pending"
    if mission.launch_location and isinstance(mission.launch_location, dict):
        location_summary = (
            mission.launch_location.get("properties", {}).get("label")
            or mission.launch_location.get("type")
            or "Mission area provided"
        )
    return MissionHistoryItem(
        mission_id=mission.id,
        purpose=mission.purpose,
        location_summary=location_summary,
        drone_id=mission.drone_id,
        decision=DecisionStatus(mission.latest_decision) if mission.latest_decision else None,
        policy_version=(mission.evaluations[-1].decision_payload or {}).get("policy_version")
        if mission.evaluations
        else None,
        evaluation_timestamp=mission.evaluation_timestamp,
        start_time=mission.start_time,
        updated_at=mission.updated_at,
    )


def conversation_to_schema(message: MissionConversationMessage) -> ConversationMessage:
    return ConversationMessage(
        message_id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )

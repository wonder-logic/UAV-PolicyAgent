from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from policy_agent.utils.datetime_utils import utcnow


def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class UserAccount(TimestampMixin, Base):
    __tablename__ = "user_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(160))

    profile: Mapped["UserPolicyProfile | None"] = relationship(back_populates="user", uselist=False)
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    credentials: Mapped[list["ProfileCredential"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    drones: Mapped[list["DroneProfile"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    missions: Mapped[list["Mission"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[UserAccount] = relationship(back_populates="sessions")


class UserPolicyProfile(TimestampMixin, Base):
    __tablename__ = "user_policy_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False)
    operator_type: Mapped[str] = mapped_column(String(80), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(160))
    preferred_units: Mapped[str] = mapped_column(String(40), default="imperial", nullable=False)
    remote_pilot_certificate_number: Mapped[str | None] = mapped_column(String(80))
    remote_pilot_certificate_issue_date: Mapped[date | None] = mapped_column(Date)
    remote_pilot_certificate_expiration: Mapped[date | None] = mapped_column(Date)
    recurrent_training_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrent_training_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped[UserAccount] = relationship(back_populates="profile")
    credentials: Mapped[list["ProfileCredential"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class ProfileCredential(TimestampMixin, Base):
    __tablename__ = "profile_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("user_policy_profiles.id", ondelete="CASCADE"), index=True)
    credential_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(120), nullable=False)
    identifier: Mapped[str | None] = mapped_column(String(120))
    issuing_authority: Mapped[str] = mapped_column(String(120), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unverified")
    restrictions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    uploaded_document_reference: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="user")

    user: Mapped[UserAccount] = relationship(back_populates="credentials")
    profile: Mapped[UserPolicyProfile] = relationship(back_populates="credentials")


class DroneProfile(TimestampMixin, Base):
    __tablename__ = "drone_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    nickname: Mapped[str] = mapped_column(String(120), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(120))
    registration_number: Mapped[str | None] = mapped_column(String(120))
    weight_grams: Mapped[float | None] = mapped_column(Float)
    maximum_takeoff_weight_grams: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(80))
    remote_id_type: Mapped[str | None] = mapped_column(String(80))
    remote_id_serial_number: Mapped[str | None] = mapped_column(String(120))
    anti_collision_lighting: Mapped[bool | None] = mapped_column(Boolean)
    light_visibility_statute_miles: Mapped[float | None] = mapped_column(Float)
    maximum_endurance_minutes: Mapped[int | None] = mapped_column(Integer)
    maximum_operating_altitude_ft: Mapped[int | None] = mapped_column(Integer)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unverified")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner: Mapped[UserAccount] = relationship(back_populates="drones")
    missions: Mapped[list["Mission"]] = relationship(back_populates="drone")


class Mission(TimestampMixin, Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    drone_id: Mapped[str] = mapped_column(ForeignKey("drone_profiles.id", ondelete="RESTRICT"), index=True)
    purpose: Mapped[str] = mapped_column(String(240), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    launch_location: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    operational_area: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    maximum_altitude_agl_ft: Mapped[float | None] = mapped_column(Float)
    maximum_distance_from_pilot_m: Mapped[float | None] = mapped_column(Float)
    operation_over_people: Mapped[bool | None] = mapped_column(Boolean)
    operation_over_moving_vehicles: Mapped[bool | None] = mapped_column(Boolean)
    visual_line_of_sight: Mapped[bool | None] = mapped_column(Boolean)
    night_operation: Mapped[bool | None] = mapped_column(Boolean)
    expected_people_count: Mapped[int | None] = mapped_column(Integer)
    controlled_ground_area: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="draft")
    latest_decision: Mapped[str | None] = mapped_column(String(40))
    evaluation_timestamp: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="missions")
    drone: Mapped[DroneProfile] = relationship(back_populates="missions")
    conversations: Mapped[list["MissionConversationMessage"]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list["MissionEvaluation"]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
    )


class MissionConversationMessage(Base):
    __tablename__ = "mission_conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_update: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    mission: Mapped[Mission] = relationship(back_populates="conversations")


class MissionEvaluation(TimestampMixin, Base):
    __tablename__ = "mission_evaluations"
    __table_args__ = (UniqueConstraint("mission_id", "idempotency_key", name="uq_mission_eval_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(60), nullable=False)
    knowledge_request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    knowledge_response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    policy_evaluations_payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    decision_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    simulator_package_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    explanation_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    mission: Mapped[Mission] = relationship(back_populates="evaluations")

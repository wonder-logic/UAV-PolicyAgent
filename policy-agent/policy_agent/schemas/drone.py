from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from policy_agent.schemas.common import TimestampedModel, VerificationStatus


class DroneProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str = Field(min_length=1, max_length=120)
    manufacturer: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=120)
    weight_grams: float | None = Field(default=None, ge=0)
    maximum_takeoff_weight_grams: float | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, max_length=80)
    remote_id_type: str | None = Field(default=None, max_length=80)
    remote_id_serial_number: str | None = Field(default=None, max_length=120)
    anti_collision_lighting: bool | None = None
    light_visibility_statute_miles: float | None = Field(default=None, ge=0)
    maximum_endurance_minutes: int | None = Field(default=None, ge=0)
    maximum_operating_altitude_ft: int | None = Field(default=None, ge=0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    is_default: bool = False


class DroneProfileCreate(DroneProfileBase):
    pass


class DroneProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, min_length=1, max_length=120)
    manufacturer: str | None = Field(default=None, min_length=1, max_length=120)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=120)
    weight_grams: float | None = Field(default=None, ge=0)
    maximum_takeoff_weight_grams: float | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, max_length=80)
    remote_id_type: str | None = Field(default=None, max_length=80)
    remote_id_serial_number: str | None = Field(default=None, max_length=120)
    anti_collision_lighting: bool | None = None
    light_visibility_statute_miles: float | None = Field(default=None, ge=0)
    maximum_endurance_minutes: int | None = Field(default=None, ge=0)
    maximum_operating_altitude_ft: int | None = Field(default=None, ge=0)
    verification_status: VerificationStatus | None = None
    is_default: bool | None = None


class DroneProfileRead(DroneProfileBase, TimestampedModel):
    drone_id: str
    owner_user_id: str

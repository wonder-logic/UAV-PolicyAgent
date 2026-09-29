from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from policy_agent.schemas.common import TimestampedModel, VerificationStatus

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserPolicyProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=120)
    email: str
    jurisdiction: str = Field(min_length=2, max_length=80)
    operator_type: str = Field(min_length=2, max_length=80)
    organization: str | None = Field(default=None, max_length=160)
    preferred_units: str = Field(default="imperial", max_length=40)
    remote_pilot_certificate_number: str | None = Field(default=None, max_length=80)
    remote_pilot_certificate_issue_date: date | None = None
    remote_pilot_certificate_expiration: date | None = None
    recurrent_training_completed: bool = False
    recurrent_training_date: date | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class UserPolicyProfileCreate(UserPolicyProfileBase):
    pass


class UserPolicyProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = None
    jurisdiction: str | None = Field(default=None, min_length=2, max_length=80)
    operator_type: str | None = Field(default=None, min_length=2, max_length=80)
    organization: str | None = Field(default=None, max_length=160)
    preferred_units: str | None = Field(default=None, max_length=40)
    remote_pilot_certificate_number: str | None = Field(default=None, max_length=80)
    remote_pilot_certificate_issue_date: date | None = None
    remote_pilot_certificate_expiration: date | None = None
    recurrent_training_completed: bool | None = None
    recurrent_training_date: date | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class CredentialRecordBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_kind: str = Field(
        description="High-level category such as certification, authorization, waiver, or training.",
        min_length=2,
        max_length=60,
    )
    credential_type: str = Field(min_length=2, max_length=120)
    identifier: str | None = Field(default=None, max_length=120)
    issuing_authority: str = Field(min_length=2, max_length=120)
    issue_date: date | None = None
    expiration_date: date | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    restrictions: list[str] = Field(default_factory=list)
    uploaded_document_reference: str | None = Field(default=None, max_length=255)
    source: str = Field(default="user", max_length=80)


class CredentialRecordCreate(CredentialRecordBase):
    pass


class CredentialRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_kind: str | None = Field(default=None, min_length=2, max_length=60)
    credential_type: str | None = Field(default=None, min_length=2, max_length=120)
    identifier: str | None = Field(default=None, max_length=120)
    issuing_authority: str | None = Field(default=None, min_length=2, max_length=120)
    issue_date: date | None = None
    expiration_date: date | None = None
    verification_status: VerificationStatus | None = None
    restrictions: list[str] | None = None
    uploaded_document_reference: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=80)


class CredentialRecordRead(CredentialRecordBase, TimestampedModel):
    credential_id: str


class UserPolicyProfileRead(UserPolicyProfileBase, TimestampedModel):
    user_id: str
    waivers: list[CredentialRecordRead] = Field(default_factory=list)
    authorizations: list[CredentialRecordRead] = Field(default_factory=list)
    certifications: list[CredentialRecordRead] = Field(default_factory=list)

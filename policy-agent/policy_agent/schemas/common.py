from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

JsonObject = dict[str, Any]
GeoJsonValue = dict[str, Any]
T = TypeVar("T")


class VerificationSource(StrEnum):
    USER = "user"
    PROFILE = "profile"
    DRONE_CATALOG = "drone_catalog"
    CERTIFICATE = "certificate"
    KNOWLEDGE_AGENT = "knowledge_agent"
    POLICY_AGENT = "policy_agent"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    PENDING = "pending"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class DecisionStatus(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PolicyEvaluationResult(StrEnum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
    AUTHORIZATION_REQUIRED = "authorization_required"
    WAIVER_REQUIRED = "waiver_required"
    NOT_APPLICABLE = "not_applicable"


class PolicyRuleSeverity(StrEnum):
    BLOCKING = "blocking"
    REVIEW = "review"
    INFORMATIONAL = "informational"


class MissionWorkflowState(StrEnum):
    DRAFT = "draft"
    COLLECTING_INFORMATION = "collecting_information"
    READY_FOR_KNOWLEDGE_AGENT = "ready_for_knowledge_agent"
    WAITING_FOR_KNOWLEDGE_AGENT = "waiting_for_knowledge_agent"
    RETRIEVING_POLICIES = "retrieving_policies"
    EVALUATING = "evaluating"
    GENERATING_GRID = "generating_grid"
    GENERATING_EXPLANATION = "generating_explanation"
    COMPLETED = "completed"
    FAILED = "failed"


class VerifiedValue(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    value: T | None = None
    source: VerificationSource
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PolicyCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str
    source: str
    authority: str
    title: str
    section: str | None = None
    paragraph: str | None = None
    page: int | None = None
    effective_date: date | None = None
    expiration_date: date | None = None
    version: str
    source_url: str | None = None
    excerpt: str
    applicability_tags: list[str] = Field(default_factory=list)


class TimestampedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    updated_at: datetime


def validate_geojson(value: GeoJsonValue | None) -> GeoJsonValue | None:
    if value is None:
        return None
    if not isinstance(value, dict) or "type" not in value:
        raise ValueError("GeoJSON-compatible objects must be dictionaries with a 'type' field.")
    return value


class GeoJsonModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: GeoJsonValue | None = None

    @field_validator("value")
    @classmethod
    def _validate_geojson(cls, value: GeoJsonValue | None) -> GeoJsonValue | None:
        return validate_geojson(value)

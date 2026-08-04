from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from policy_agent.schemas.common import GeoJsonValue, VerificationStatus, validate_geojson


class KnowledgeMissionFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    value: str | bool | float | int | dict | list | None
    source: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    warnings: list[str] = Field(default_factory=list)


class KnowledgeCellFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    status: str = "known"
    facts: list[KnowledgeMissionFact] = Field(default_factory=list)
    traversal_cost: float = Field(default=1.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)


class KnowledgeAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    mission_id: str
    location: GeoJsonValue | None = None
    operational_area: GeoJsonValue | None = None
    mission_time_start: datetime | None = None
    mission_time_end: datetime | None = None
    altitude_ft: float | None = Field(default=None, ge=0)
    drone_characteristics: dict[str, object] = Field(default_factory=dict)
    requested_context_categories: list[str] = Field(default_factory=list)
    grid_cells: list[dict[str, object]] = Field(default_factory=list)

    @field_validator("location", "operational_area")
    @classmethod
    def _validate_geojson(
        cls,
        value: GeoJsonValue | None,
    ) -> GeoJsonValue | None:
        return validate_geojson(value)


class KnowledgeAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    mission_id: str
    mission_level_facts: list[KnowledgeMissionFact] = Field(default_factory=list)
    cell_level_facts: list[KnowledgeCellFact] = Field(default_factory=list)
    source: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

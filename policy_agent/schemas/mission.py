from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from policy_agent.schemas.common import (
    DecisionStatus,
    GeoJsonValue,
    MissionWorkflowState,
    PolicyCitation,
    TimestampedModel,
    validate_geojson,
)
from policy_agent.schemas.knowledge import KnowledgeAgentResponse
from policy_agent.schemas.policy import PolicyEvaluation


class MissionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drone_id: str
    purpose: str = Field(min_length=2, max_length=240)
    start_time: datetime | None = None
    end_time: datetime | None = None
    launch_location: GeoJsonValue | None = None
    operational_area: GeoJsonValue | None = None
    maximum_altitude_agl_ft: float | None = Field(default=None, ge=0)
    maximum_distance_from_pilot_m: float | None = Field(default=None, ge=0)
    operation_over_people: bool | None = None
    operation_over_moving_vehicles: bool | None = None
    visual_line_of_sight: bool | None = None
    night_operation: bool | None = None
    expected_people_count: int | None = Field(default=None, ge=0)
    controlled_ground_area: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("launch_location", "operational_area")
    @classmethod
    def _validate_geojson(
        cls,
        value: GeoJsonValue | None,
    ) -> GeoJsonValue | None:
        return validate_geojson(value)


class MissionCreate(MissionBase):
    pass


class MissionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str | None = Field(default=None, min_length=2, max_length=240)
    drone_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    launch_location: GeoJsonValue | None = None
    operational_area: GeoJsonValue | None = None
    maximum_altitude_agl_ft: float | None = Field(default=None, ge=0)
    maximum_distance_from_pilot_m: float | None = Field(default=None, ge=0)
    operation_over_people: bool | None = None
    operation_over_moving_vehicles: bool | None = None
    visual_line_of_sight: bool | None = None
    night_operation: bool | None = None
    expected_people_count: int | None = Field(default=None, ge=0)
    controlled_ground_area: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("launch_location", "operational_area")
    @classmethod
    def _validate_geojson(
        cls,
        value: GeoJsonValue | None,
    ) -> GeoJsonValue | None:
        return validate_geojson(value)


class MissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    launch_location: GeoJsonValue | None = None
    operational_area: GeoJsonValue | None = None
    maximum_altitude_agl_ft: float | None = Field(default=None, ge=0)
    maximum_distance_from_pilot_m: float | None = Field(default=None, ge=0)
    operation_over_people: bool | None = None
    operation_over_moving_vehicles: bool | None = None
    visual_line_of_sight: bool | None = None
    night_operation: bool | None = None
    expected_people_count: int | None = Field(default=None, ge=0)
    controlled_ground_area: bool | None = None
    notes: str | None = None

    @field_validator("launch_location", "operational_area")
    @classmethod
    def _validate_geojson(
        cls,
        value: GeoJsonValue | None,
    ) -> GeoJsonValue | None:
        return validate_geojson(value)


class MissionUpdateExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updates: MissionUpdate = Field(default_factory=MissionUpdate)
    uncertain_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None
    reasoning_summary: str | None = None


class MissionDetailsRead(MissionBase, TimestampedModel):
    mission_id: str
    user_id: str
    status: MissionWorkflowState
    latest_decision: DecisionStatus | None = None
    evaluation_timestamp: datetime | None = None


class MissionHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    purpose: str
    location_summary: str
    drone_id: str
    decision: DecisionStatus | None = None
    policy_version: str | None = None
    evaluation_timestamp: datetime | None = None
    start_time: datetime | None = None
    updated_at: datetime


class MissionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    decision: DecisionStatus
    concise_summary: str
    narrative_explanation: str | None = None
    policy_evaluations: list[PolicyEvaluation] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    citations: list[PolicyCitation] = Field(default_factory=list)
    evaluation_timestamp: datetime
    policy_version: str


class SimulatorGridCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    status: str
    traversal_cost: float = Field(ge=0.0)
    triggered_rule_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    citations: list[PolicyCitation] = Field(default_factory=list)


class SimulatorPolicyPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    grid_version: str
    overall_decision: DecisionStatus
    generated_timestamp: datetime
    policy_version: str
    grid_cells: list[SimulatorGridCell] = Field(default_factory=list)


class MissionCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission: MissionDetailsRead
    user_profile: dict[str, object]
    selected_drone: dict[str, object]
    knowledge_response: KnowledgeAgentResponse | None = None
    policy_evaluations: list[PolicyEvaluation] = Field(default_factory=list)
    decision: MissionDecision | None = None
    conversation_state: dict[str, object] = Field(default_factory=dict)
    timestamps: dict[str, datetime] = Field(default_factory=dict)


class MissionEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = None
    grid_cells: list[dict[str, object]] = Field(default_factory=list)


class MissionSubmissionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission: MissionDetailsRead
    missing_fields: list[str] = Field(default_factory=list)
    ready_for_evaluation: bool

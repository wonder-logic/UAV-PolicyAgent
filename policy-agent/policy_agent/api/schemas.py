from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DroneCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    manufacturer: str
    model_name: str
    uas_class: str | None = None
    weight_grams: float | None = None
    max_takeoff_weight_grams: float | None = None
    endurance_minutes: float | None = None
    night_lights: bool | None = None
    anti_collision_lights: bool | None = None
    has_camera: bool | None = None
    is_toy: bool | None = None


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str | None = None
    subject_role: str | None = None

    drone_model_id: str | None = None
    drone_manufacturer: str | None = None
    drone_model: str | None = None
    uas_class: str | None = None
    drone_weight_grams: float | None = None
    max_takeoff_weight_grams: float | None = None
    endurance_minutes: float | None = None
    night_lights: bool | None = None
    anti_collision_lights: bool | None = None
    has_camera: bool | None = None
    is_toy: bool | None = None

    operation_type: Literal[
        "recreational",
        "commercial",
        "research",
        "public_safety",
        "unknown",
    ] = "unknown"

    origin_location: str | None = None
    destination_location: str | None = None
    live_location: str | None = None
    intended_flight_time: str | None = None

    altitude_ft: float | None = None
    speed_mph: float | None = None

    over_people: bool | None = None
    over_moving_vehicles: bool | None = None
    night_operation: bool | None = None
    controlled_airspace: bool | None = None
    controlled_airspace_authorization_provided: bool | None = None
    visual_line_of_sight: bool | None = None
    remote_id_available: bool | None = None
    pilot_certification_provided: bool | None = None

    mission_purpose: str | None = None
    local_restrictions_known: bool | None = None
    additional_context: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class IngestResponse(BaseModel):
    documents_loaded: int
    chunks_indexed: int
    vector_backend: str
    policy_directory: str


class PolicySearchResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]


class PolicyAssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str | None = None
    policy_request: PolicyRequest
    include_decision_preview: bool = True


class PolicyAssistResponse(BaseModel):
    assistant_message: str
    ready_for_decision: bool
    missing_attributes: list[str]
    questions: list[str]
    enriched_request: PolicyRequest
    drone_profile: DroneCatalogEntry | None = None
    catalog_warnings: list[str] = Field(default_factory=list)
    preview_decision: dict[str, Any] | None = None


class KnowledgeDroneContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    uas_class: str | None = None
    weight_in_grams: str | float | int | None = None
    max_takeoff_in_grams: str | float | int | None = None
    endurance_in_mins: str | float | int | None = None
    night_light: bool | None = None
    anti_collision: bool | None = None
    has_camera: bool | None = None
    maximum_operating_altitude_ft: str | float | int | None = None
    manufacturer: str | None = None


class KnowledgeLocationContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    original_input: str | None = None
    normalized_location: str | None = None
    resolved_location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None


class KnowledgeZoneContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None


class KnowledgeWeatherContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    temperature: float | None = None
    temperature_unit: str | None = None
    wind_speed: float | None = None
    wind_gusts: float | None = None
    wind_direction: str | None = None
    visibility: float | None = None
    precipitation: float | None = None
    weather: str | None = None


class KnowledgeReasoningContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    missing_information: list[str] = Field(default_factory=list)


class MissionKnowledgeContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent: str | None = None
    current_time: str | None = None
    drone: KnowledgeDroneContext | None = None
    battery_percent: float | int | None = None
    start_location: str | None = None
    destination: str | None = None
    start_coordinates: KnowledgeLocationContext | None = None
    destination_coordinates: KnowledgeLocationContext | None = None
    restricted_zones: list[KnowledgeZoneContext] = Field(default_factory=list)
    human_zones: list[KnowledgeZoneContext] = Field(default_factory=list)
    start_weather: KnowledgeWeatherContext | None = None
    destination_weather: KnowledgeWeatherContext | None = None
    weather_warning: list[str] = Field(default_factory=list)
    start_lookup_status: str | None = None
    destination_lookup_status: str | None = None
    terrain: dict[str, Any] = Field(default_factory=dict)
    knowledge_reasoning: KnowledgeReasoningContext | None = None


class PolicyChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    policy_request: PolicyRequest = Field(default_factory=PolicyRequest)
    include_decision_preview: bool = True
    knowledge_context: MissionKnowledgeContext | None = None


class PolicyChatEvaluationStage(StrEnum):
    COLLECTING_INFORMATION = "COLLECTING_INFORMATION"
    PRELIMINARY = "PRELIMINARY"
    KNOWLEDGE_PENDING = "KNOWLEDGE_PENDING"
    FINAL = "FINAL"
    ERROR = "ERROR"


class PolicyKnowledgeSource(StrEnum):
    SUPPLIED = "SUPPLIED"
    KNOWLEDGE_AGENT = "KNOWLEDGE_AGENT"
    MOCK = "MOCK"
    NONE = "NONE"


class PolicyChatDecisionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["APPROVED", "DENIED", "NEEDS_REVIEW"] | None = None
    summary: str | None = None
    explanation: str | None = None
    rule_results: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    mission_score: int | None = None
    accuracy_score: int | None = None
    confidence: str | None = None
    matched_policies: list[str] = Field(default_factory=list)


class PolicyChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_message: str
    evaluation_stage: PolicyChatEvaluationStage = PolicyChatEvaluationStage.PRELIMINARY
    knowledge_agent_called: bool = False
    knowledge_source: PolicyKnowledgeSource = PolicyKnowledgeSource.NONE
    policy_request: PolicyRequest
    verified_mission_context: dict[str, Any] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    grounded_facts: list[str] = Field(default_factory=list)
    decision: PolicyChatDecisionSummary | None = None
    knowledge_request: dict[str, Any] | None = None
    knowledge_response: dict[str, Any] | None = None
    spatial_constraints: list[dict[str, Any]] = Field(default_factory=list)
    simulator_package: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    extracted_fields: list[str] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)
    next_question: str | None = None
    ready_for_decision: bool
    final_decision_ready: bool
    verified_facts: list[str] = Field(default_factory=list)
    catalog_warnings: list[str] = Field(default_factory=list)
    knowledge_context_used: bool = False
    knowledge_warnings: list[str] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    knowledge_follow_up_questions: list[str] = Field(default_factory=list)
    preview_decision: dict[str, Any] | None = None
    knowledge_request_preview: dict[str, Any] | None = None
    simulator_grid_preview: dict[str, Any] | None = None


class PolicyGridCell(BaseModel):
    model_config = ConfigDict(extra="allow")

    cell_id: str
    x_index: int | None = None
    y_index: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    altitude_ft: float | None = None
    speed_mph: float | None = None
    over_people: bool | None = None
    over_moving_vehicles: bool | None = None
    night_operation: bool | None = None
    controlled_airspace: bool | None = None
    controlled_airspace_authorization_provided: bool | None = None
    visual_line_of_sight: bool | None = None
    remote_id_available: bool | None = None
    pilot_certification_provided: bool | None = None
    local_restrictions_known: bool | None = None
    additional_context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyGridRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_request: PolicyRequest
    grid_cells: list[PolicyGridCell] = Field(min_length=1)


class PolicyGridCellDecision(BaseModel):
    cell_id: str
    x_index: int | None = None
    y_index: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    blocked: bool
    cost: float
    policy_decision: Literal["PERMIT", "DENY", "NOT_APPLICABLE", "INDETERMINATE"]
    uavguard_status: Literal["APPROVED", "DENIED", "NEEDS_REVIEW"]
    warnings: list[str]
    missing_attributes: list[str]
    citations: list[dict[str, Any]]
    explanation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyGridResponse(BaseModel):
    base_request_decision: dict[str, Any]
    simulator_recommendation: Literal["PROCEED", "BLOCK", "REVIEW"]
    total_cells: int
    no_fly_zone_cell_ids: list[str]
    allowed_cell_ids: list[str]
    review_cell_ids: list[str]
    cells: list[PolicyGridCellDecision]

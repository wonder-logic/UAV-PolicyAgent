"""Pydantic schemas shared across the API and agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DecisionStatus = Literal["APPROVED", "DENIED", "NEEDS_REVIEW"]
PolicyStatus = Literal["COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW"]


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class ResolvedLocation(BaseModel):
    query: str
    coordinates: Coordinates | None = None
    source: str
    warnings: list[str] = Field(default_factory=list)


class FlightRequest(BaseModel):
    manufacturer: str
    model: str
    origin: str
    destination: str
    battery_percentage: int = Field(ge=0, le=100)
    intended_flight_time: str
    mission_purpose: str | None = None

    @property
    def origin_location(self) -> str:
        return self.origin

    @property
    def destination_location(self) -> str:
        return self.destination

    @property
    def current_battery_percentage(self) -> int:
        return self.battery_percentage


class DroneProfile(BaseModel):
    manufacturer: str
    model: str
    weight_grams: float | None = None
    max_flight_time_minutes: float | None = None
    max_range_meters: float | None = None
    max_speed_mps: float | None = None
    source: str = "unknown"
    match_type: str = "unresolved"
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class WeatherSnapshot(BaseModel):
    temperature_c: float
    wind_speed_mps: float
    weather_code: int | None = None
    source: str
    warnings: list[str] = Field(default_factory=list)


class FeasibilityAssessment(BaseModel):
    status: DecisionStatus
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)


class KnowledgeAssessment(BaseModel):
    status: DecisionStatus
    lookup_query: str
    match_type: str
    resolved_origin: ResolvedLocation
    resolved_destination: ResolvedLocation
    distance_meters: float | None = None
    route_distance_meters: float | None = None
    weather: WeatherSnapshot
    feasibility: FeasibilityAssessment
    warnings: list[str] = Field(default_factory=list)


class PolicyCitation(BaseModel):
    source: str
    chunk_id: str
    snippet: str


class PolicyChunk(BaseModel):
    chunk_id: str
    source: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyAssessment(BaseModel):
    policy_status: PolicyStatus
    matched_rules: list[str] = Field(default_factory=list)
    explanation: str
    citations: list[PolicyCitation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SimulationAssessment(BaseModel):
    status: DecisionStatus
    path_found: bool | None = None
    warnings: list[str] = Field(default_factory=list)
    grid_cell_size_meters: float | None = None
    restricted_cell_count: int = 0
    path: list[list[int]] = Field(default_factory=list)
    mission: dict[str, Any] = Field(default_factory=dict)
    visualization_path: str | None = None


class ArtifactPaths(BaseModel):
    mission_file: str
    grid_visualization: str


class FlightDecisionResponse(BaseModel):
    request: FlightRequest
    drone_profile: DroneProfile
    knowledge_assessment: KnowledgeAssessment
    policy_assessment: PolicyAssessment
    simulation_assessment: SimulationAssessment
    final_decision: DecisionStatus
    explanation: str
    artifacts: ArtifactPaths


class IngestResponse(BaseModel):
    status: str
    items_indexed: int
    detail: str


class DroneSearchMatch(BaseModel):
    manufacturer: str
    model: str
    score: float
    source: str


class DroneSearchResponse(BaseModel):
    query: str
    matches: list[DroneSearchMatch] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    database_path: str
    policy_docs_dir: str
    indexed_policy_collection: str

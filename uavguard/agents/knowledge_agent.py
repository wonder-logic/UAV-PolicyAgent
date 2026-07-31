"""Knowledge Base Agent for drone specs, geocoding, and feasibility."""

from __future__ import annotations

from ..api.schemas import (
    Coordinates,
    DroneProfile,
    FlightRequest,
    KnowledgeAssessment,
    ResolvedLocation,
    WeatherSnapshot,
)
from ..config.settings import Settings, get_settings
from ..knowledge_base.drone_repository import DroneRepository
from ..knowledge_base.feasibility import assess_feasibility
from ..knowledge_base.geospatial import estimate_route_distance_meters, geodesic_distance_meters, resolve_location
from ..knowledge_base.weather import fetch_weather


class KnowledgeBaseAgent:
    """Resolve the operational context required for a mission decision."""

    def __init__(self, settings: Settings | None = None, repository: DroneRepository | None = None) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or DroneRepository(self.settings)

    def _fallback_weather(self) -> WeatherSnapshot:
        return WeatherSnapshot(
            temperature_c=self.settings.weather_fallback_temperature_c,
            wind_speed_mps=self.settings.weather_fallback_wind_speed_mps,
            source="fallback",
            warnings=["Weather lookup skipped because the origin could not be resolved."],
        )

    def run(self, request: FlightRequest) -> tuple[DroneProfile, KnowledgeAssessment]:
        """Execute the knowledge pipeline for a flight request."""

        lookup = self.repository.lookup(request.manufacturer, request.model)
        origin = resolve_location(request.origin_location, self.settings)
        destination = resolve_location(request.destination_location, self.settings)

        distance_meters: float | None = None
        route_distance_meters: float | None = None
        if origin.coordinates is not None and destination.coordinates is not None:
            distance_meters = geodesic_distance_meters(origin.coordinates, destination.coordinates)
            route_distance_meters = estimate_route_distance_meters(distance_meters)

        weather = fetch_weather(origin.coordinates, self.settings) if origin.coordinates else self._fallback_weather()
        feasibility = assess_feasibility(request, lookup.profile, route_distance_meters, weather)

        warnings = list(lookup.warnings)
        warnings.extend(origin.warnings)
        warnings.extend(destination.warnings)
        warnings.extend(weather.warnings)

        if feasibility.status == "DENIED":
            status = "DENIED"
        elif warnings or feasibility.status == "NEEDS_REVIEW":
            status = "NEEDS_REVIEW"
        else:
            status = "APPROVED"

        assessment = KnowledgeAssessment(
            status=status,
            lookup_query=f"{request.manufacturer} {request.model}",
            match_type=lookup.match_type,
            resolved_origin=origin,
            resolved_destination=destination,
            distance_meters=distance_meters,
            route_distance_meters=route_distance_meters,
            weather=weather,
            feasibility=feasibility,
            warnings=warnings,
        )
        return lookup.profile, assessment

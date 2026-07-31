"""Prompt-like query builders for conservative policy retrieval."""

from __future__ import annotations

from ..api.schemas import DroneProfile, FlightRequest, KnowledgeAssessment


def build_policy_query(
    request: FlightRequest,
    drone_profile: DroneProfile,
    knowledge_assessment: KnowledgeAssessment,
) -> str:
    """Build a retrieval query from the structured request context."""

    return (
        "FAA drone compliance review for "
        f"{drone_profile.manufacturer} {drone_profile.model}. "
        f"Origin: {request.origin_location}. Destination: {request.destination_location}. "
        f"Battery: {request.current_battery_percentage} percent. "
        f"Mission purpose: {request.mission_purpose or 'not provided'}. "
        f"Intended time: {request.intended_flight_time}. "
        f"Estimated route distance: {knowledge_assessment.route_distance_meters or 'unknown'} meters. "
        "Focus on operational constraints, visual line of sight, daylight/night operations, "
        "authorizations, and prohibited flight conditions."
    )

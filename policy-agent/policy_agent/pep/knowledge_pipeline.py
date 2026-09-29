from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from policy_agent.api.schemas import (
    KnowledgeLocationContext,
    KnowledgeWeatherContext,
    MissionKnowledgeContext,
    PolicyRequest,
)
from policy_agent.utils.json_utils import unique_in_order
from policy_agent.utils.text_utils import normalize_whitespace

LOW_BATTERY_WARNING_THRESHOLD = 30.0
HIGH_WIND_WARNING_THRESHOLD_MPH = 20.0
HIGH_GUST_WARNING_THRESHOLD_MPH = 25.0

BLOCKING_KNOWLEDGE_QUESTIONS = {
    "no_start_location_found": "Can you confirm the launch point with a more specific location name?",
    "no_destination_found": "Can you confirm the destination with a more specific location name?",
}

REFINEMENT_KNOWLEDGE_QUESTIONS = {
    "max_distance": "What is the farthest distance the aircraft will get from the pilot?",
    "max_airspeed": "What is the maximum planned airspeed for the mission?",
    "min_altitude": "What is the minimum planned altitude for the route?",
}

KNOWLEDGE_GAP_LABELS = {
    "no_start_location_found": "a confirmed launch point",
    "no_destination_found": "a confirmed destination",
    "max_distance": "the farthest distance from the pilot",
    "max_airspeed": "the maximum planned airspeed",
    "min_altitude": "the minimum planned altitude",
}


@dataclass(slots=True)
class KnowledgeContextMerge:
    updated_request: PolicyRequest
    extracted_fields: list[str]
    verified_facts: list[str]
    warnings: list[str]
    blocking_questions: list[str]
    refinement_questions: list[str]
    knowledge_gaps: list[str]


def summarize_missing_information(
    missing_information: list[str],
    *,
    start_lookup_status: str | None = None,
    destination_lookup_status: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    blocking_questions: list[str] = []
    refinement_questions: list[str] = []
    knowledge_gaps: list[str] = []

    normalized_start_status = (start_lookup_status or "").strip().upper()
    normalized_destination_status = (destination_lookup_status or "").strip().upper()

    for token in missing_information:
        if token == "no_start_location_found" and normalized_start_status == "SUCCESS":
            continue
        if token == "no_destination_found" and normalized_destination_status == "SUCCESS":
            continue

        knowledge_gaps.append(_humanize_gap(token))
        if token in BLOCKING_KNOWLEDGE_QUESTIONS:
            blocking_questions.append(BLOCKING_KNOWLEDGE_QUESTIONS[token])
        elif token in REFINEMENT_KNOWLEDGE_QUESTIONS:
            refinement_questions.append(REFINEMENT_KNOWLEDGE_QUESTIONS[token])

    return (
        unique_in_order(knowledge_gaps),
        unique_in_order(blocking_questions),
        unique_in_order(refinement_questions),
    )


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _clean_location_label(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = normalize_whitespace(value)
    if not cleaned:
        return None
    if " becomes " in cleaned.casefold():
        parts = [part.strip() for part in cleaned.split("becomes") if part.strip()]
        if parts:
            return parts[-1]
    return cleaned


def _best_location_label(
    location_context: KnowledgeLocationContext | None,
    fallback: str | None,
) -> str | None:
    candidates = [
        location_context.normalized_location if location_context else None,
        fallback,
        location_context.original_input if location_context else None,
        location_context.resolved_location if location_context else None,
    ]
    for candidate in candidates:
        cleaned = _clean_location_label(candidate)
        if cleaned:
            return cleaned
    return None


def _weather_fact(prefix: str, weather: KnowledgeWeatherContext | None) -> str | None:
    if weather is None:
        return None

    parts: list[str] = []
    if weather.weather:
        parts.append(weather.weather)
    if weather.wind_speed is not None:
        parts.append(f"{weather.wind_speed:.1f} mph winds")
    if weather.wind_gusts is not None:
        parts.append(f"gusts to {weather.wind_gusts:.1f} mph")

    if not parts:
        return None
    return f"{prefix}: {', '.join(parts)}"


def _weather_warning(prefix: str, weather: KnowledgeWeatherContext | None) -> str | None:
    if weather is None:
        return None
    if weather.wind_speed is None and weather.wind_gusts is None:
        return None
    wind_speed = weather.wind_speed or 0.0
    wind_gusts = weather.wind_gusts or 0.0
    if wind_speed < HIGH_WIND_WARNING_THRESHOLD_MPH and wind_gusts < HIGH_GUST_WARNING_THRESHOLD_MPH:
        return None
    return (
        f"{prefix} weather shows elevated wind: {wind_speed:.1f} mph sustained"
        f" and {wind_gusts:.1f} mph gusts."
    )


def _humanize_gap(token: str) -> str:
    return KNOWLEDGE_GAP_LABELS.get(token, token.replace("_", " "))


def merge_knowledge_context(
    *,
    current_request: PolicyRequest,
    knowledge_context: MissionKnowledgeContext | None,
) -> KnowledgeContextMerge:
    if knowledge_context is None:
        return KnowledgeContextMerge(
            updated_request=current_request,
            extracted_fields=[],
            verified_facts=[],
            warnings=[],
            blocking_questions=[],
            refinement_questions=[],
            knowledge_gaps=[],
        )

    updates: dict[str, object] = {}
    verified_facts: list[str] = []
    warnings: list[str] = []
    blocking_questions: list[str] = []
    refinement_questions: list[str] = []
    knowledge_gaps: list[str] = []

    drone = knowledge_context.drone
    if drone is not None:
        if drone.manufacturer:
            updates["drone_manufacturer"] = drone.manufacturer
        if drone.name:
            updates["drone_model"] = drone.name
        if drone.uas_class:
            updates["uas_class"] = drone.uas_class
        weight_grams = _coerce_float(drone.weight_in_grams)
        if weight_grams is not None:
            updates["drone_weight_grams"] = weight_grams
        max_takeoff = _coerce_float(drone.max_takeoff_in_grams)
        if max_takeoff is not None:
            updates["max_takeoff_weight_grams"] = max_takeoff
        endurance = _coerce_float(drone.endurance_in_mins)
        if endurance is not None:
            updates["endurance_minutes"] = endurance
        if drone.anti_collision is not None:
            updates["anti_collision_lights"] = drone.anti_collision
        if drone.has_camera is not None:
            updates["has_camera"] = drone.has_camera

        aircraft_parts = [part for part in [drone.manufacturer, drone.name] if part]
        if aircraft_parts:
            verified_facts.append(f"Knowledge context aircraft: {' '.join(aircraft_parts)}")

    origin_label = _best_location_label(knowledge_context.start_coordinates, knowledge_context.start_location)
    if origin_label:
        updates["origin_location"] = origin_label
        updates["live_location"] = origin_label
        verified_facts.append(f"Launch point resolved: {origin_label}")

    destination_label = _best_location_label(knowledge_context.destination_coordinates, knowledge_context.destination)
    if destination_label:
        updates["destination_location"] = destination_label
        verified_facts.append(f"Destination resolved: {destination_label}")

    battery_percent = _coerce_float(knowledge_context.battery_percent)
    if battery_percent is not None:
        verified_facts.append(f"Battery reported: {battery_percent:.0f}%")
        if battery_percent < LOW_BATTERY_WARNING_THRESHOLD:
            warnings.append(
                f"Battery reported by the Knowledge Agent is only {battery_percent:.0f}%, which deserves an operational recheck."
            )

    launch_weather_fact = _weather_fact("Launch weather", knowledge_context.start_weather)
    if launch_weather_fact:
        verified_facts.append(launch_weather_fact)
    destination_weather_fact = _weather_fact("Destination weather", knowledge_context.destination_weather)
    if destination_weather_fact:
        verified_facts.append(destination_weather_fact)

    for weather_warning in knowledge_context.weather_warning:
        rendered = normalize_whitespace(weather_warning)
        if rendered:
            warnings.append(rendered)

    launch_wind_warning = _weather_warning("Launch", knowledge_context.start_weather)
    if launch_wind_warning:
        warnings.append(launch_wind_warning)
    destination_wind_warning = _weather_warning("Destination", knowledge_context.destination_weather)
    if destination_wind_warning:
        warnings.append(destination_wind_warning)

    restricted_zone_names = [zone.name for zone in knowledge_context.restricted_zones if zone.name]
    if restricted_zone_names:
        preview_names = ", ".join(restricted_zone_names[:3])
        warnings.append(
            "Knowledge context identified nearby airport or military-sensitive locations that still need route-level review: "
            f"{preview_names}."
        )
        verified_facts.append(f"Nearby sensitive airspace references: {len(restricted_zone_names)}")

    human_zone_names = [zone.name for zone in knowledge_context.human_zones if zone.name]
    if human_zone_names:
        verified_facts.append(f"Nearby population-sensitive sites identified: {len(human_zone_names)}")

    missing_information = knowledge_context.knowledge_reasoning.missing_information if knowledge_context.knowledge_reasoning else []
    knowledge_gaps, blocking_questions, refinement_questions = summarize_missing_information(
        missing_information,
        start_lookup_status=knowledge_context.start_lookup_status,
        destination_lookup_status=knowledge_context.destination_lookup_status,
    )

    merged_request = current_request.model_copy(update=updates)

    return KnowledgeContextMerge(
        updated_request=merged_request,
        extracted_fields=sorted(updates.keys()),
        verified_facts=unique_in_order(verified_facts)[:8],
        warnings=unique_in_order(warnings),
        blocking_questions=unique_in_order(blocking_questions),
        refinement_questions=unique_in_order(refinement_questions),
        knowledge_gaps=unique_in_order(knowledge_gaps),
    )


def compute_grounding_scores(
    *,
    preview_decision: dict[str, object] | None,
    knowledge_context_used: bool,
    knowledge_blocker_count: int,
    knowledge_refinement_count: int,
    knowledge_warning_count: int,
) -> tuple[int | None, int | None]:
    if preview_decision is None:
        return None, None

    decision_status = str(preview_decision.get("uavguard_status") or "")
    confidence = str(preview_decision.get("confidence") or "")
    missing_attributes = cast(list[Any], preview_decision.get("missing_attributes", []) or [])
    citations = cast(list[Any], preview_decision.get("citations", []) or [])

    mission_base = {
        "APPROVED": 88,
        "NEEDS_REVIEW": 62,
        "DENIED": 28,
    }.get(decision_status, 50)
    mission_score = mission_base
    mission_score -= len(missing_attributes) * 10
    mission_score -= knowledge_blocker_count * 10
    mission_score -= knowledge_refinement_count * 3
    mission_score -= min(knowledge_warning_count, 4) * 3

    accuracy_base = {
        "HIGH": 92,
        "MEDIUM": 78,
        "LOW": 64,
    }.get(confidence, 60)
    accuracy_score = accuracy_base
    accuracy_score += min(len(citations), 3) * 4
    accuracy_score += 5 if knowledge_context_used else 0
    accuracy_score -= len(missing_attributes) * 12
    accuracy_score -= knowledge_blocker_count * 10
    accuracy_score -= knowledge_refinement_count * 3
    if not citations:
        accuracy_score -= 12

    return max(0, min(100, mission_score)), max(0, min(100, accuracy_score))

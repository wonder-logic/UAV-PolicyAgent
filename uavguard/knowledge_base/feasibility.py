"""Rule-based mission feasibility evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ..api.schemas import DroneProfile, FeasibilityAssessment, FlightRequest, WeatherSnapshot


MISSION_FACTORS: Final[dict[str, float]] = {
    "inspection": 1.05,
    "mapping": 1.10,
    "survey": 1.08,
    "delivery": 1.18,
    "emergency": 1.15,
}


def _estimate_nominal_range(drone_profile: DroneProfile) -> float | None:
    if drone_profile.max_range_meters:
        return drone_profile.max_range_meters
    if drone_profile.max_speed_mps and drone_profile.max_flight_time_minutes:
        return drone_profile.max_speed_mps * drone_profile.max_flight_time_minutes * 60 * 0.45
    return None


def _extract_mission_factor(mission_purpose: str | None) -> float:
    if not mission_purpose:
        return 1.0
    purpose = mission_purpose.lower()
    for key, factor in MISSION_FACTORS.items():
        if key in purpose:
            return factor
    return 1.0


def _is_night_operation(intended_flight_time: str) -> bool:
    try:
        parsed = datetime.fromisoformat(intended_flight_time)
    except ValueError:
        return False
    return parsed.hour < 6 or parsed.hour >= 20


def assess_feasibility(
    request: FlightRequest,
    drone_profile: DroneProfile,
    route_distance_meters: float | None,
    weather: WeatherSnapshot,
) -> FeasibilityAssessment:
    """Evaluate operational feasibility using a conservative rule set."""

    reasons: list[str] = []
    warnings: list[str] = list(drone_profile.warnings) + list(weather.warnings)
    metrics: dict[str, float | int | str | bool | None] = {
        "battery_percentage": request.current_battery_percentage,
        "route_distance_meters": route_distance_meters,
        "wind_speed_mps": weather.wind_speed_mps,
        "temperature_c": weather.temperature_c,
    }

    nominal_range_meters = _estimate_nominal_range(drone_profile)
    metrics["nominal_range_meters"] = nominal_range_meters
    reserve_percentage = 20
    mission_factor = _extract_mission_factor(request.mission_purpose)
    metrics["mission_factor"] = mission_factor
    metrics["night_operation"] = _is_night_operation(request.intended_flight_time)

    if request.current_battery_percentage < 15:
        reasons.append("Battery percentage is below the minimum 15% emergency threshold.")
    elif request.current_battery_percentage < reserve_percentage:
        warnings.append("Battery percentage is below the preferred 20% reserve margin.")

    if nominal_range_meters is None:
        warnings.append("Drone range could not be estimated from available specifications.")
    elif route_distance_meters is not None:
        wind_multiplier = 1.0 + max(weather.wind_speed_mps - 5.0, 0.0) * 0.03
        adjusted_energy_pct = (
            (route_distance_meters / nominal_range_meters) * 100 * wind_multiplier * mission_factor
        )
        usable_battery_pct = max(request.current_battery_percentage - reserve_percentage, 0)
        battery_limited_range = nominal_range_meters * usable_battery_pct / 100
        metrics["wind_multiplier"] = round(wind_multiplier, 3)
        metrics["estimated_energy_required_pct"] = round(adjusted_energy_pct, 2)
        metrics["usable_battery_pct"] = usable_battery_pct
        metrics["battery_limited_range_meters"] = round(battery_limited_range, 2)

        if adjusted_energy_pct > usable_battery_pct:
            reasons.append("Estimated mission energy exceeds the available battery after reserve.")
        elif adjusted_energy_pct > usable_battery_pct * 0.85:
            warnings.append("Mission energy usage is close to the available battery reserve.")

    if weather.wind_speed_mps >= 14:
        reasons.append("Wind speed is too high for a conservative mission approval.")
    elif weather.wind_speed_mps >= 10:
        warnings.append("Wind speed is elevated and should be reviewed manually.")

    if weather.temperature_c <= -10 or weather.temperature_c >= 40:
        reasons.append("Temperature is outside the safe operating envelope.")
    elif weather.temperature_c <= 0 or weather.temperature_c >= 35:
        warnings.append("Temperature is near a conservative operating limit.")

    if drone_profile.weight_grams and drone_profile.weight_grams > 25_000:
        reasons.append("Drone weight exceeds the supported small-UAS research profile.")

    if route_distance_meters is None:
        warnings.append("Route distance is unavailable because geocoding did not complete.")

    if metrics["night_operation"]:
        warnings.append("Night or late-evening operations require policy review.")

    if reasons:
        status = "DENIED"
    elif warnings:
        status = "NEEDS_REVIEW"
    else:
        status = "APPROVED"

    return FeasibilityAssessment(
        status=status,
        reasons=reasons,
        warnings=warnings,
        metrics=metrics,
    )

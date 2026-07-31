"""Weather accessors with Open-Meteo and safe fallback behavior."""

from __future__ import annotations

import httpx

from ..api.schemas import Coordinates, WeatherSnapshot
from ..config.settings import Settings, get_settings


def fetch_weather(
    coordinates: Coordinates,
    settings: Settings | None = None,
) -> WeatherSnapshot:
    """Fetch weather data for a coordinate pair."""

    resolved_settings = settings or get_settings()
    try:
        response = httpx.get(
            resolved_settings.open_meteo_url,
            params={
                "latitude": coordinates.latitude,
                "longitude": coordinates.longitude,
                "current": "temperature_2m,wind_speed_10m,weather_code",
                "wind_speed_unit": "ms",
            },
            timeout=resolved_settings.weather_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current", {})
        return WeatherSnapshot(
            temperature_c=float(current.get("temperature_2m", resolved_settings.weather_fallback_temperature_c)),
            wind_speed_mps=float(current.get("wind_speed_10m", resolved_settings.weather_fallback_wind_speed_mps)),
            weather_code=int(current["weather_code"]) if current.get("weather_code") is not None else None,
            source="open-meteo",
        )
    except Exception as exc:  # pragma: no cover - depends on network access
        return WeatherSnapshot(
            temperature_c=resolved_settings.weather_fallback_temperature_c,
            wind_speed_mps=resolved_settings.weather_fallback_wind_speed_mps,
            weather_code=None,
            source="fallback",
            warnings=[
                "Open-Meteo weather lookup failed; using placeholder weather values.",
                str(exc),
            ],
        )

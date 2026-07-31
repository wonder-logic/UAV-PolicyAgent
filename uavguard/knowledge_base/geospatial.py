"""Geospatial helpers with offline-friendly fallbacks."""

from __future__ import annotations

from math import asin, atan2, cos, radians, sin, sqrt
from typing import Final

try:
    from geopy.geocoders import Nominatim
except ImportError:  # pragma: no cover - optional dependency
    Nominatim = None

from ..api.schemas import Coordinates, ResolvedLocation
from ..config.settings import Settings, get_settings


KNOWN_LOCATIONS: Final[dict[str, tuple[float, float]]] = {
    "xavier university of louisiana, new orleans, la": (29.9655, -90.1070),
    "audubon park, new orleans, la": (29.9325, -90.1229),
    "new orleans, la": (29.9511, -90.0715),
    "torrance, ca": (33.8358, -118.3406),
    "corpus christi, tx": (27.8006, -97.3964),
    "texas a&m university corpus christi, corpus christi, tx": (27.7129, -97.3232),
    "el camino community college, torrance, ca": (33.8853, -118.3269),
}


def _parse_coordinate_pair(value: str) -> Coordinates | None:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return None
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError:
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return Coordinates(latitude=latitude, longitude=longitude)


def resolve_location(location: str, settings: Settings | None = None) -> ResolvedLocation:
    """Resolve a human-readable location into coordinates."""

    resolved_settings = settings or get_settings()
    coordinate_pair = _parse_coordinate_pair(location)
    if coordinate_pair is not None:
        return ResolvedLocation(
            query=location,
            coordinates=coordinate_pair,
            source="inline_coordinates",
        )

    normalized = " ".join(location.lower().split())
    if normalized in KNOWN_LOCATIONS:
        lat, lon = KNOWN_LOCATIONS[normalized]
        return ResolvedLocation(
            query=location,
            coordinates=Coordinates(latitude=lat, longitude=lon),
            source="offline_lookup",
        )

    if Nominatim is not None:
        try:
            geolocator = Nominatim(user_agent=resolved_settings.geocoder_user_agent, timeout=5)
            result = geolocator.geocode(location)
            if result is not None:
                return ResolvedLocation(
                    query=location,
                    coordinates=Coordinates(latitude=result.latitude, longitude=result.longitude),
                    source="geopy_nominatim",
                )
        except Exception as exc:  # pragma: no cover - network failures are nondeterministic
            return ResolvedLocation(
                query=location,
                coordinates=None,
                source="geocoder_error",
                warnings=[f"Geocoding failed: {exc}"],
            )

    return ResolvedLocation(
        query=location,
        coordinates=None,
        source="unresolved",
        warnings=[
            "Location could not be geocoded. Provide coordinates or add the location to the offline map.",
        ],
    )


def geodesic_distance_meters(origin: Coordinates, destination: Coordinates) -> float:
    """Compute geodesic distance with the haversine formula."""

    earth_radius_m = 6_371_000
    lat1 = radians(origin.latitude)
    lat2 = radians(destination.latitude)
    delta_lat = radians(destination.latitude - origin.latitude)
    delta_lon = radians(destination.longitude - origin.longitude)
    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return earth_radius_m * c


def estimate_route_distance_meters(distance_meters: float, route_factor: float = 1.12) -> float:
    """Pad a straight-line distance to approximate a safer mission route."""

    return distance_meters * route_factor


def relative_offset_meters(origin: Coordinates, destination: Coordinates) -> tuple[float, float]:
    """Return east/north displacement in meters."""

    average_lat = radians((origin.latitude + destination.latitude) / 2)
    north_m = (destination.latitude - origin.latitude) * 111_320
    east_m = (destination.longitude - origin.longitude) * 111_320 * cos(average_lat)
    return east_m, north_m

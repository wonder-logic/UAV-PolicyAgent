"""Future MAVSDK integration surface."""

from __future__ import annotations


def prepare_mavsdk_mission(mission: dict) -> dict:
    """Return a placeholder MAVSDK mission wrapper."""

    return {
        "status": "stub",
        "message": "MAVSDK integration is not enabled in the lightweight prototype yet.",
        "mission": mission,
    }

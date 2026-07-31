"""Future Gazebo integration surface."""

from __future__ import annotations


def prepare_gazebo_scenario(mission: dict) -> dict:
    """Return a placeholder Gazebo scenario wrapper."""

    return {
        "status": "stub",
        "message": "Gazebo integration is reserved for a future simulator bridge.",
        "mission": mission,
    }

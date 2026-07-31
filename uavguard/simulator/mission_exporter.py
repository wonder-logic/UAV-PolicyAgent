"""Mission export helpers for simulator-ready artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _stringify_grid(grid: dict[tuple[int, int], int]) -> dict[str, int]:
    return {str((x, y)): allowed for (x, y), allowed in grid.items()}


def build_mission_payload(
    grid: dict[tuple[int, int], int],
    start: tuple[int, int],
    goal: tuple[int, int],
    path: list[tuple[int, int]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the simulator-ready mission dictionary."""

    return {
        "grid": _stringify_grid(grid),
        "start": list(start),
        "goal": list(goal),
        "path": [list(cell) for cell in path],
        "metadata": metadata or {},
    }


def save_mission_file(mission: dict[str, Any], output_path: str | Path) -> str:
    """Persist a mission file to JSON."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mission, indent=2), encoding="utf-8")
    return str(path)

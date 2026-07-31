"""Drone data ingestion from OpenDroneList-style JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from contextlib import closing

from .db import get_connection, initialize_database


def _coerce_number(value: Any) -> float | None:
    if value in (None, "", "unknown"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iter_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("drones", "items", "results", "data"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
        return [payload]
    return []


def normalize_drone_record(record: dict[str, Any], source: str) -> dict[str, Any] | None:
    """Map loosely structured JSON into the UAVGuard drone schema."""

    manufacturer = (
        record.get("manufacturer")
        or record.get("brand")
        or record.get("maker")
        or record.get("company")
    )
    model = record.get("model") or record.get("name") or record.get("aircraft_model")
    if not manufacturer or not model:
        return None

    return {
        "manufacturer": str(manufacturer).strip(),
        "model": str(model).strip(),
        "weight_grams": _coerce_number(
            record.get("weight_grams")
            or record.get("weight")
            or record.get("mass_grams")
        ),
        "max_flight_time_minutes": _coerce_number(
            record.get("max_flight_time_minutes")
            or record.get("flight_time")
            or record.get("endurance_minutes")
        ),
        "max_range_meters": _coerce_number(
            record.get("max_range_meters")
            or record.get("range_meters")
            or record.get("max_distance")
        ),
        "max_speed_mps": _coerce_number(
            record.get("max_speed_mps")
            or record.get("speed_mps")
            or record.get("max_speed")
        ),
        "source": str(record.get("source") or source),
    }


def ingest_json_file(json_path: str | Path, database_path: str | Path) -> int:
    """Load a JSON file and upsert drone records into SQLite."""

    initialize_database(database_path)
    path = Path(json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized_records = [
        normalized
        for normalized in (
            normalize_drone_record(record, path.name)
            for record in _iter_records(payload)
        )
        if normalized is not None
    ]
    if not normalized_records:
        return 0

    with closing(get_connection(database_path)) as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO drones (
                manufacturer,
                model,
                weight_grams,
                max_flight_time_minutes,
                max_range_meters,
                max_speed_mps,
                source
            ) VALUES (
                :manufacturer,
                :model,
                :weight_grams,
                :max_flight_time_minutes,
                :max_range_meters,
                :max_speed_mps,
                :source
            )
            """,
            normalized_records,
        )
        connection.commit()
    return len(normalized_records)


def ingest_directory(raw_dir: str | Path, database_path: str | Path) -> int:
    """Ingest every JSON file under a raw data directory."""

    total = 0
    for path in sorted(Path(raw_dir).glob("*.json")):
        total += ingest_json_file(path, database_path)
    return total

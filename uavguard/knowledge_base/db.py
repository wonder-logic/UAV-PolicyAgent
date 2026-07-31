"""SQLite helpers for UAVGuard drone metadata."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS drones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer TEXT NOT NULL,
    model TEXT NOT NULL,
    weight_grams REAL,
    max_flight_time_minutes REAL,
    max_range_meters REAL,
    max_speed_mps REAL,
    source TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_drones_unique
    ON drones (manufacturer, model, source);

CREATE INDEX IF NOT EXISTS idx_drones_manufacturer_model
    ON drones (manufacturer, model);
"""


def get_connection(database_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_path: str | Path) -> None:
    """Ensure the drone schema exists."""

    with closing(get_connection(database_path)) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()

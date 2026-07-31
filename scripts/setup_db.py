"""Initialize the UAVGuard drone database and ingest sample data."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uavguard.config import get_settings
from uavguard.knowledge_base.db import initialize_database
from uavguard.knowledge_base.ingest_drones import ingest_directory


def main() -> None:
    settings = get_settings()
    initialize_database(settings.database_path)
    count = ingest_directory(settings.raw_data_dir, settings.database_path)
    print(f"Initialized database at {settings.database_path}")
    print(f"Ingested {count} drone records from {settings.raw_data_dir}")


if __name__ == "__main__":
    main()

"""Index FAA policy documents for UAVGuard."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uavguard.config import get_settings
from uavguard.policy.ingest_policies import ingest_policy_directory


def main() -> None:
    settings = get_settings()
    count = ingest_policy_directory(settings.faa_docs_dir, settings)
    print(f"Indexed {count} policy chunks from {settings.faa_docs_dir}")


if __name__ == "__main__":
    main()

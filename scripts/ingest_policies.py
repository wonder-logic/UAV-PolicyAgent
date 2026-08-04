from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from policy_agent.config import build_settings
from policy_agent.pap.policy_repository import PolicyRepository
from policy_agent.utils.logging import configure_logging


def main() -> None:
    settings = build_settings(PROJECT_ROOT)
    settings.ensure_directories()
    configure_logging(settings.log_level)

    repository = PolicyRepository(settings)
    summary = repository.ingest()
    print(json.dumps(summary.model_dump(), indent=2))


if __name__ == "__main__":
    main()

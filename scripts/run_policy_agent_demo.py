from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from policy_agent.api.schemas import PolicyRequest
from policy_agent.config import build_settings
from policy_agent.pep.enforcement_point import PolicyEnforcementPoint
from policy_agent.retrieval.document_loader import discover_document_sources
from policy_agent.utils.logging import configure_logging


def _ensure_demo_policy(settings) -> None:
    policy_sources = discover_document_sources(settings.policy_docs_dir)
    if policy_sources:
        return

    sample_policy = settings.sample_policies_dir / "research_night_operations_policy.txt"
    if sample_policy.exists():
        shutil.copy2(sample_policy, settings.policy_docs_dir / sample_policy.name)
        return

    fallback_policy = """# Demo Research Night Operations Policy

## Night Operations
Night operations may operate for research missions only when Remote ID is active, visual line of sight is maintained, and the operator provides pilot certification evidence.

## Controlled Airspace
Operations in controlled airspace require documented authorization before flight.

## Altitude
Flights must not exceed 400 feet above ground level unless a specific waiver is documented.
"""
    (settings.policy_docs_dir / "demo_policy.txt").write_text(fallback_policy, encoding="utf-8")


def _load_demo_request(settings) -> PolicyRequest:
    sample_request_path = settings.sample_requests_dir / "demo_request.json"
    if sample_request_path.exists():
        return PolicyRequest.model_validate_json(sample_request_path.read_text(encoding="utf-8"))

    return PolicyRequest(
        subject_id="test-user",
        subject_role="student_researcher",
        drone_manufacturer="DJI",
        drone_model="Mini 4 Pro",
        drone_weight_grams=249,
        operation_type="research",
        origin_location="Texas A&M University-Corpus Christi",
        destination_location="Corpus Christi Bay",
        intended_flight_time="night",
        altitude_ft=350,
        speed_mph=20,
        over_people=False,
        night_operation=True,
        controlled_airspace=None,
        visual_line_of_sight=None,
        remote_id_available=True,
        pilot_certification_provided=None,
        mission_purpose="research data collection",
        local_restrictions_known=None,
        additional_context="Demo request for UAVGuard Policy Agent.",
    )


def main() -> None:
    settings = build_settings(PROJECT_ROOT)
    settings.ensure_directories()
    configure_logging(settings.log_level)

    _ensure_demo_policy(settings)
    pep = PolicyEnforcementPoint(settings)
    pep.ingest_policies()

    decision = pep.evaluate_request(_load_demo_request(settings))
    print(json.dumps(decision.model_dump(), indent=2))


if __name__ == "__main__":
    main()

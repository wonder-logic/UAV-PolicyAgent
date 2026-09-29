from __future__ import annotations

from policy_agent.pap.policy_metadata import PolicyDocument
from policy_agent.utils.text_utils import clean_text

BUILTIN_PART107_BASELINE = """
# UAVGuard Built-in Part 107 Baseline

## Pilot Certification
Research and commercial small UAS missions require a remote pilot in command who is covered by a valid Part 107 remote pilot certificate.

## Remote ID
When Remote ID applies, the mission should use active Remote ID throughout the operation.

## Night Operations
Night operations require anti-collision lighting and continued visual line of sight. The remote pilot or visual observer must be able to keep the aircraft in sight during the operation.

## Controlled Airspace
Operations in Class B, C, D, or qualifying Class E airspace require prior Air Traffic Control authorization.

## Altitude
The aircraft must not exceed 400 feet above ground level unless a valid structure-based exception applies.

## Operations Over People
Flights should not operate directly over uninvolved people unless the mission qualifies for the applicable allowance or waiver path.

## Local Site Considerations
Local campus, property, or site restrictions should be confirmed before flight.
"""


def builtin_policy_documents() -> list[PolicyDocument]:
    return [
        PolicyDocument(
            document_name="uavguard_part107_baseline.md",
            source_path="builtin://uavguard/part107-baseline",
            file_type="md",
            content=clean_text(BUILTIN_PART107_BASELINE),
            pages=[],
        )
    ]

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from policy_agent.schemas.common import PolicyCitation


@dataclass(frozen=True, slots=True)
class TrustedCitationRecord:
    citation_id: str
    source: str
    authority: str
    title: str
    section: str
    paragraph: str | None
    page: int | None
    effective_date: date | None
    expiration_date: date | None
    version: str
    source_url: str | None
    excerpt: str
    applicability_tags: tuple[str, ...]


TRUSTED_CITATIONS: dict[str, TrustedCitationRecord] = {
    "part107_altitude": TrustedCitationRecord(
        citation_id="part107_altitude",
        source="14 CFR Part 107",
        authority="FAA",
        title="Operating limitations for small unmanned aircraft",
        section="14 CFR 107.51(b)",
        paragraph=None,
        page=11,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Small unmanned aircraft generally may not fly higher than 400 feet above ground level.",
        applicability_tags=("altitude", "mission_limit"),
    ),
    "part107_pilot_cert": TrustedCitationRecord(
        citation_id="part107_pilot_cert",
        source="14 CFR Part 107",
        authority="FAA",
        title="Requirement for remote pilot certificate",
        section="14 CFR 107.12(a)(1)",
        paragraph=None,
        page=6,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="A person manipulating the controls of a small UAS must hold the required remote pilot credential.",
        applicability_tags=("pilot", "certificate"),
    ),
    "part107_night": TrustedCitationRecord(
        citation_id="part107_night",
        source="14 CFR Part 107",
        authority="FAA",
        title="Night operations",
        section="14 CFR 107.29(a)",
        paragraph=None,
        page=8,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Night operations require the remote pilot to meet FAA night-operation conditions and training requirements.",
        applicability_tags=("night", "training"),
    ),
    "part107_lighting": TrustedCitationRecord(
        citation_id="part107_lighting",
        source="14 CFR Part 107",
        authority="FAA",
        title="Night anti-collision lighting",
        section="14 CFR 107.29(a)(2)",
        paragraph=None,
        page=8,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Night flights require anti-collision lighting visible for at least 3 statute miles.",
        applicability_tags=("night", "lighting"),
    ),
    "part107_airspace": TrustedCitationRecord(
        citation_id="part107_airspace",
        source="14 CFR Part 107",
        authority="FAA",
        title="Operation in certain airspace",
        section="14 CFR 107.41",
        paragraph=None,
        page=10,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Operations in Class B, C, D, or designated Class E airspace require prior ATC authorization.",
        applicability_tags=("airspace", "authorization"),
    ),
    "part107_over_people": TrustedCitationRecord(
        citation_id="part107_over_people",
        source="14 CFR Part 107",
        authority="FAA",
        title="Operation over human beings",
        section="14 CFR 107.39",
        paragraph=None,
        page=10,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Operations over people are limited unless the operation meets a permitted category or approved exception.",
        applicability_tags=("people", "waiver"),
    ),
    "part107_moving_vehicles": TrustedCitationRecord(
        citation_id="part107_moving_vehicles",
        source="14 CFR Part 107",
        authority="FAA",
        title="Operations over moving vehicles",
        section="14 CFR 107.145",
        paragraph=None,
        page=19,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Sustained flight over moving vehicles is prohibited unless specific conditions are met.",
        applicability_tags=("vehicles", "waiver"),
    ),
    "part89_remote_id": TrustedCitationRecord(
        citation_id="part89_remote_id",
        source="14 CFR Part 89",
        authority="FAA",
        title="Remote identification operating requirements",
        section="14 CFR 89.105",
        paragraph=None,
        page=12,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-89",
        excerpt="Most small unmanned aircraft operations must comply with applicable Remote ID requirements.",
        applicability_tags=("remote_id", "aircraft"),
    ),
    "part107_vlos": TrustedCitationRecord(
        citation_id="part107_vlos",
        source="14 CFR Part 107",
        authority="FAA",
        title="Visual line of sight",
        section="14 CFR 107.31",
        paragraph=None,
        page=9,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="The aircraft must remain within visual line of sight of the remote pilot, visual observer, or person manipulating the controls.",
        applicability_tags=("vlos", "waiver"),
    ),
    "part107_waiver": TrustedCitationRecord(
        citation_id="part107_waiver",
        source="14 CFR Part 107",
        authority="FAA",
        title="Waiver authority",
        section="14 CFR 107.200",
        paragraph=None,
        page=23,
        effective_date=date(2024, 12, 30),
        expiration_date=None,
        version="2024-12-30",
        source_url="https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107",
        excerpt="Certain operating limitations may be waived when the FAA grants and the operator complies with the waiver terms.",
        applicability_tags=("waiver", "exception"),
    ),
}


def citation_from_record(record: TrustedCitationRecord) -> PolicyCitation:
    return PolicyCitation(
        citation_id=record.citation_id,
        source=record.source,
        authority=record.authority,
        title=record.title,
        section=record.section,
        paragraph=record.paragraph,
        page=record.page,
        effective_date=record.effective_date,
        expiration_date=record.expiration_date,
        version=record.version,
        source_url=record.source_url,
        excerpt=record.excerpt,
        applicability_tags=list(record.applicability_tags),
    )


def get_trusted_citation(citation_id: str) -> PolicyCitation:
    return citation_from_record(TRUSTED_CITATIONS[citation_id])

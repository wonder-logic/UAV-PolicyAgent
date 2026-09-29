from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.pdp.decision import Citation, PDPDecision
from policy_agent.utils.json_utils import unique_in_order

PART_107_DOCUMENT = "14 CFR Part 107 (up to date as of 12-30-2024).pdf"


def _build_citation(*, section: str, page: int, text_snippet: str) -> Citation:
    return Citation(
        document=PART_107_DOCUMENT,
        section=section,
        page=page,
        text_snippet=text_snippet,
        relevance="Deterministic Part 107 safeguard applied by the policy engine.",
    )


def _merge_citations(primary: list[Citation], secondary: list[Citation]) -> list[Citation]:
    merged: list[Citation] = []
    seen: set[tuple[str, str | None, int | None, str]] = set()

    for citation in [*primary, *secondary]:
        key = (citation.document, citation.section, citation.page, citation.text_snippet)
        if key in seen:
            continue
        seen.add(key)
        merged.append(citation)

    return merged


def apply_part107_hard_rules(policy_request: PolicyRequest, decision: PDPDecision) -> PDPDecision:
    matched_policies: list[str] = []
    obligations: list[str] = []
    advice: list[str] = []
    warnings: list[str] = []
    citations: list[Citation] = []
    explanations: list[str] = []

    if policy_request.altitude_ft is not None and policy_request.altitude_ft > 400:
        matched_policies.append(f"{PART_107_DOCUMENT}#14 CFR 107.51(b)")
        obligations.append(
            "Reduce the planned altitude to 400 feet AGL or confirm that the applicable structure exception applies."
        )
        citations.append(
            _build_citation(
                section="14 CFR 107.51(b)",
                page=11,
                text_snippet=(
                    "The altitude of the small unmanned aircraft cannot be higher than 400 feet above ground "
                    "level unless it remains within 400 feet of a structure and no more than 400 feet above it."
                ),
            )
        )
        explanations.append(
            "14 CFR 107.51(b) blocks this mission because the requested altitude exceeds 400 feet above ground level and no structure-based exception was supplied."
        )

    if policy_request.speed_mph is not None and policy_request.speed_mph > 100:
        matched_policies.append(f"{PART_107_DOCUMENT}#14 CFR 107.51(a)")
        obligations.append("Reduce groundspeed to 100 mph or less.")
        citations.append(
            _build_citation(
                section="14 CFR 107.51(a)",
                page=11,
                text_snippet="The groundspeed of the small unmanned aircraft may not exceed 87 knots (100 miles per hour).",
            )
        )
        explanations.append("14 CFR 107.51(a) blocks this mission because the requested speed exceeds 100 mph.")

    if policy_request.night_operation is True and policy_request.anti_collision_lights is False:
        matched_policies.append(f"{PART_107_DOCUMENT}#14 CFR 107.29(a)(2)")
        obligations.append("Equip the aircraft with anti-collision lighting visible for at least 3 statute miles.")
        citations.append(
            _build_citation(
                section="14 CFR 107.29(a)(2)",
                page=8,
                text_snippet=(
                    "No person may operate a small unmanned aircraft system at night unless the small unmanned "
                    "aircraft has lighted anti-collision lighting visible for at least 3 statute miles."
                ),
            )
        )
        explanations.append(
            "14 CFR 107.29(a)(2) blocks this mission because night operations require anti-collision lighting."
        )

    if policy_request.visual_line_of_sight is False:
        matched_policies.append(f"{PART_107_DOCUMENT}#14 CFR 107.31")
        obligations.append("Maintain visual line of sight throughout the flight or use an approved waiver workflow.")
        citations.append(
            _build_citation(
                section="14 CFR 107.31",
                page=9,
                text_snippet=(
                    "The remote pilot in command, visual observer, or person manipulating the flight controls "
                    "must be able to see the unmanned aircraft throughout the entire flight."
                ),
            )
        )
        explanations.append(
            "14 CFR 107.31 blocks this mission because the aircraft must remain within visual line of sight throughout the operation."
        )

    if (
        policy_request.controlled_airspace is True
        and policy_request.controlled_airspace_authorization_provided is False
    ):
        matched_policies.append(f"{PART_107_DOCUMENT}#14 CFR 107.41")
        obligations.append(
            "Obtain prior Air Traffic Control authorization for the controlled-airspace portion of the mission."
        )
        citations.append(
            _build_citation(
                section="14 CFR 107.41",
                page=10,
                text_snippet=(
                    "No person may operate a small unmanned aircraft in Class B, C, D, or qualifying Class E "
                    "airspace unless that person has prior authorization from Air Traffic Control."
                ),
            )
        )
        explanations.append(
            "14 CFR 107.41 blocks this mission because the request enters controlled airspace without prior ATC authorization."
        )

    if (
        policy_request.operation_type in {"commercial", "research"}
        and policy_request.pilot_certification_provided is False
    ):
        matched_policies.extend(
            [
                f"{PART_107_DOCUMENT}#14 CFR 107.12(a)(1)",
                f"{PART_107_DOCUMENT}#14 CFR 107.19(b)",
            ]
        )
        obligations.append("Use a pilot who is covered by the required Part 107 remote pilot certificate.")
        citations.extend(
            [
                _build_citation(
                    section="14 CFR 107.12(a)(1)",
                    page=6,
                    text_snippet=(
                        "No person may manipulate the flight controls of a small unmanned aircraft system unless "
                        "that person has a remote pilot certificate with a small UAS rating."
                    ),
                ),
                _build_citation(
                    section="14 CFR 107.19(b)",
                    page=7,
                    text_snippet=(
                        "No person may act as a remote pilot in command unless that person has a remote pilot "
                        "certificate with a small UAS rating."
                    ),
                ),
            ]
        )
        explanations.append(
            "14 CFR 107.12 and 107.19 block this mission because the submitted research or commercial flight does not confirm the required remote pilot certification."
        )

    if not explanations:
        return decision

    combined_explanations = unique_in_order([*explanations, decision.explanation])
    combined_warnings = unique_in_order(
        [
            *decision.warnings,
            *warnings,
            "Deterministic Part 107 safeguards marked one or more mission constraints as non-compliant.",
        ]
    )
    combined_obligations = unique_in_order([*decision.obligations, *obligations])
    combined_advice = unique_in_order([*decision.advice, *advice])
    combined_policies = unique_in_order([*decision.matched_policies, *matched_policies])
    combined_citations = _merge_citations(citations, decision.citations)
    confidence = "HIGH" if len(explanations) > 1 else "MEDIUM"

    return decision.model_copy(
        update={
            "decision": "DENY",
            "uavguard_status": "DENIED",
            "matched_policies": combined_policies,
            "obligations": combined_obligations,
            "advice": combined_advice,
            "warnings": combined_warnings,
            "citations": combined_citations,
            "explanation": " ".join(combined_explanations),
            "confidence": confidence,
        }
    )

"""Conservative policy evaluation based on retrieved chunks."""

from __future__ import annotations

from datetime import datetime

from ..api.schemas import (
    DroneProfile,
    FlightRequest,
    KnowledgeAssessment,
    PolicyAssessment,
    PolicyCitation,
)
from ..config.settings import Settings, get_settings
from .prompts import build_policy_query
from .retriever import PolicyRetriever


class PolicyEvaluator:
    """Retrieve FAA policy excerpts and derive a conservative assessment."""

    def __init__(self, settings: Settings | None = None, retriever: PolicyRetriever | None = None) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or PolicyRetriever(self.settings)

    @staticmethod
    def _is_night_operation(intended_flight_time: str) -> bool:
        try:
            parsed = datetime.fromisoformat(intended_flight_time)
        except ValueError:
            return False
        return parsed.hour < 6 or parsed.hour >= 20

    def assess(
        self,
        request: FlightRequest,
        drone_profile: DroneProfile,
        knowledge_assessment: KnowledgeAssessment,
    ) -> PolicyAssessment:
        """Return a policy-focused assessment grounded in retrieved chunks."""

        query = build_policy_query(request, drone_profile, knowledge_assessment)
        chunks = self.retriever.query(query, limit=5)
        if not chunks:
            return PolicyAssessment(
                policy_status="NEEDS_REVIEW",
                matched_rules=[],
                explanation=(
                    "No indexed FAA policy text matched the mission request. "
                    "The flight should be reviewed manually before approval."
                ),
                citations=[],
                warnings=["Policy index is empty or no relevant policy chunks were retrieved."],
            )

        combined_text = " ".join(chunk.text.lower() for chunk in chunks)
        matched_rules: list[str] = []
        warnings: list[str] = []
        direct_conflicts: list[str] = []
        citations = [
            PolicyCitation(
                source=chunk.source,
                chunk_id=chunk.chunk_id,
                snippet=(chunk.text[:180] + "...") if len(chunk.text) > 180 else chunk.text,
            )
            for chunk in chunks
        ]

        night_operation = self._is_night_operation(request.intended_flight_time)
        if "visual line of sight" in combined_text or "vlos" in combined_text:
            matched_rules.append("Retrieved policy text references visual line-of-sight requirements.")
        if "daylight" in combined_text or "civil twilight" in combined_text or "night" in combined_text:
            matched_rules.append("Retrieved policy text references time-of-day operating constraints.")
        if "authorization" in combined_text or "waiver" in combined_text:
            matched_rules.append("Retrieved policy text references authorization or waiver requirements.")

        if night_operation:
            if "anti-collision" in combined_text or "civil twilight" in combined_text or "night" in combined_text:
                warnings.append(
                    "Night operations appear in the retrieved policy text, but required lighting or waivers were not verified."
                )
            else:
                warnings.append(
                    "The mission is scheduled at night, and no supporting night-operation rule was retrieved."
                )
            if any(
                phrase in combined_text
                for phrase in ("night operations are prohibited", "night flights are prohibited", "no night operations")
            ):
                direct_conflicts.append("Retrieved policy text explicitly prohibits night operations.")

        if knowledge_assessment.route_distance_meters and knowledge_assessment.route_distance_meters > 2_000:
            if "visual line of sight" in combined_text or "vlos" in combined_text:
                warnings.append(
                    "The route may be too long to satisfy visual line-of-sight requirements without additional controls."
                )

        mission_purpose = (request.mission_purpose or "").lower()
        if "event" in mission_purpose and any(
            phrase in combined_text
            for phrase in ("operations over people are prohibited", "flight over open-air assemblies is prohibited")
        ):
            direct_conflicts.append("Mission purpose suggests over-people operations that are prohibited in the retrieved text.")

        if direct_conflicts:
            status = "NON_COMPLIANT"
            explanation = (
                "Retrieved policy text contains a direct conflict with the requested mission profile. "
                "The flight should be denied until the conflicting rule is resolved."
            )
        elif warnings:
            status = "NEEDS_REVIEW"
            explanation = (
                "Relevant policy excerpts were found, but the available inputs are not sufficient to prove compliance. "
                "The mission should be reviewed manually."
            )
        else:
            status = "COMPLIANT"
            explanation = (
                "Relevant policy excerpts were retrieved and no direct policy conflict was detected in the indexed material. "
                "This assessment is limited to the locally indexed rules."
            )

        return PolicyAssessment(
            policy_status=status,
            matched_rules=matched_rules + direct_conflicts,
            explanation=explanation,
            citations=citations,
            warnings=warnings,
        )

"""Policy Agent for conservative FAA policy assessment."""

from __future__ import annotations

from ..api.schemas import DroneProfile, FlightRequest, KnowledgeAssessment, PolicyAssessment
from ..config.settings import Settings, get_settings
from ..policy.evaluator import PolicyEvaluator
from ..policy.ingest_policies import ingest_policy_directory
from ..policy.retriever import PolicyRetriever


class PolicyAgent:
    """Retrieve policy text and derive a conservative compliance assessment."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.retriever = PolicyRetriever(self.settings)
        self.evaluator = PolicyEvaluator(self.settings, self.retriever)

    def _ensure_index(self) -> None:
        if self.retriever.count() > 0:
            return
        has_docs = any(
            path.is_file() and path.suffix.lower() in {".txt", ".pdf"}
            for path in self.settings.faa_docs_dir.iterdir()
        )
        if has_docs:
            ingest_policy_directory(self.settings.faa_docs_dir, self.settings)

    def run(
        self,
        request: FlightRequest,
        drone_profile: DroneProfile,
        knowledge_assessment: KnowledgeAssessment,
    ) -> PolicyAssessment:
        """Return the policy assessment for a request."""

        self._ensure_index()
        return self.evaluator.assess(request, drone_profile, knowledge_assessment)

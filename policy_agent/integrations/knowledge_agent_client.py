from __future__ import annotations

from typing import Protocol

import httpx

from policy_agent.config import Settings
from policy_agent.core.exceptions import ExternalServiceError
from policy_agent.schemas.common import VerificationStatus
from policy_agent.schemas.knowledge import (
    KnowledgeAgentRequest,
    KnowledgeAgentResponse,
    KnowledgeCellFact,
    KnowledgeMissionFact,
)


class BaseKnowledgeAgentClient(Protocol):
    def fetch_facts(self, request: KnowledgeAgentRequest) -> KnowledgeAgentResponse: ...


def _coerce_float(value: object, default: float = 1.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _bool_fact(category: str, value: bool, *, source: str, confidence: float = 0.9) -> KnowledgeMissionFact:
    return KnowledgeMissionFact(
        category=category,
        value=value,
        source=source,
        confidence=confidence,
        verification_status=VerificationStatus.VERIFIED,
    )


class MockKnowledgeAgentClient:
    def fetch_facts(self, request: KnowledgeAgentRequest) -> KnowledgeAgentResponse:
        location_label = ""
        if request.location:
            location_label = str(request.location.get("properties", {}).get("label", "")).lower()

        controlled_airspace = any(
            token in location_label for token in ("airport", "class b", "class c", "class d", "class e")
        )
        restricted_area = any(token in location_label for token in ("restricted", "tfr", "stadium"))
        weather_good = True

        mission_facts = [
            _bool_fact("controlled_airspace", controlled_airspace, source="mock_knowledge_agent"),
            _bool_fact("restricted_area", restricted_area, source="mock_knowledge_agent", confidence=0.85),
            _bool_fact("weather_suitable", weather_good, source="mock_knowledge_agent", confidence=0.7),
        ]

        cell_facts: list[KnowledgeCellFact] = []
        for cell in request.grid_cells:
            facts = []
            if "controlled_airspace" in cell:
                facts.append(
                    _bool_fact(
                        "controlled_airspace",
                        bool(cell["controlled_airspace"]),
                        source="mock_knowledge_agent",
                    )
                )
            if "restricted_area" in cell:
                facts.append(
                    _bool_fact(
                        "restricted_area",
                        bool(cell["restricted_area"]),
                        source="mock_knowledge_agent",
                    )
                )
            cell_facts.append(
                KnowledgeCellFact(
                    cell_id=str(cell["cell_id"]),
                    facts=facts,
                    traversal_cost=_coerce_float(cell.get("traversal_cost", 1.0)),
                    warnings=[],
                )
            )

        warnings = []
        if restricted_area:
            warnings.append("The mission location appears to intersect a restricted or temporarily constrained area.")

        return KnowledgeAgentResponse(
            request_id=request.request_id,
            mission_id=request.mission_id,
            mission_level_facts=mission_facts,
            cell_level_facts=cell_facts,
            source="mock_knowledge_agent",
            confidence=0.82,
            verification_status=VerificationStatus.VERIFIED,
            missing_information=[],
            warnings=warnings,
        )


class HttpKnowledgeAgentClient:
    def __init__(self, settings: Settings):
        if not settings.knowledge_agent_base_url:
            raise ExternalServiceError("KNOWLEDGE_AGENT_BASE_URL is not configured.")
        self.settings = settings
        self.base_url = settings.knowledge_agent_base_url

    def fetch_facts(self, request: KnowledgeAgentRequest) -> KnowledgeAgentResponse:
        last_error: Exception | None = None
        for _ in range(self.settings.knowledge_agent_max_retries + 1):
            try:
                with httpx.Client(timeout=self.settings.knowledge_agent_timeout_seconds) as client:
                    response = client.post(
                        self.base_url,
                        json=request.model_dump(mode="json"),
                    )
                response.raise_for_status()
                return KnowledgeAgentResponse.model_validate(response.json())
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc
        raise ExternalServiceError(f"Knowledge Agent request failed: {last_error}")  # pragma: no cover


def create_knowledge_agent_client(settings: Settings) -> BaseKnowledgeAgentClient:
    if settings.knowledge_agent_mode == "remote":
        return HttpKnowledgeAgentClient(settings)
    return MockKnowledgeAgentClient()

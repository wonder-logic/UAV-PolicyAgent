from __future__ import annotations

from policy_agent.api.schemas import (
    MissionKnowledgeContext,
    PolicyAssistRequest,
    PolicyChatRequest,
    PolicyGridRequest,
    PolicyKnowledgeSource,
    PolicyRequest,
)
from policy_agent.config import Settings
from policy_agent.drone_catalog.repository import DroneCatalogRepository
from policy_agent.evaluation.rule_evaluator import evaluate_request_attributes
from policy_agent.integrations import create_knowledge_agent_client, create_llm_provider
from policy_agent.pap.policy_repository import PolicyRepository
from policy_agent.pdp.pdp import PolicyDecisionPoint
from policy_agent.pep.chat_artifacts import build_preview_grid_cells
from policy_agent.pep.chat_flow import build_policy_chat_response, extract_policy_chat_request
from policy_agent.pep.conversation_service import build_assist_response
from policy_agent.pep.grid_service import (
    build_grid_cell_decision,
    build_grid_response,
    merge_policy_request_with_cell,
)
from policy_agent.pep.knowledge_pipeline import compute_grounding_scores, merge_knowledge_context, summarize_missing_information
from policy_agent.schemas.common import VerificationStatus
from policy_agent.schemas.knowledge import KnowledgeAgentResponse, KnowledgeCellFact, KnowledgeMissionFact
from policy_agent.services.mission_evaluator import (
    SharedMissionEvaluator,
    build_chat_drone,
    build_chat_mission,
    build_chat_profile,
    build_knowledge_request,
)
from policy_agent.utils.json_utils import unique_in_order


def _knowledge_fact(
    category: str,
    value: str | bool | float | int | dict | list | None,
    *,
    source: str,
    confidence: float = 0.9,
) -> KnowledgeMissionFact:
    return KnowledgeMissionFact(
        category=category,
        value=value,
        source=source,
        confidence=confidence,
        verification_status=VerificationStatus.VERIFIED,
    )


def _normalize_supplied_knowledge_response(
    *,
    knowledge_context: MissionKnowledgeContext,
    mission_id: str,
    request_id: str,
    grid_cells,
) -> KnowledgeAgentResponse:
    mission_facts: list[KnowledgeMissionFact] = []
    source = "supplied_knowledge_context"

    if knowledge_context.restricted_zones:
        mission_facts.append(_knowledge_fact("restricted_area", True, source=source, confidence=0.95))
        if any(
            any(token in zone_type for token in ("airport", "military"))
            for zone in knowledge_context.restricted_zones
            for zone_type in zone.type
        ):
            mission_facts.append(_knowledge_fact("controlled_airspace", True, source=source, confidence=0.85))

    if knowledge_context.weather_warning:
        mission_facts.append(_knowledge_fact("weather_suitable", False, source=source, confidence=0.75))
    elif knowledge_context.start_weather or knowledge_context.destination_weather:
        mission_facts.append(_knowledge_fact("weather_suitable", True, source=source, confidence=0.7))

    cell_facts: list[KnowledgeCellFact] = []
    for cell in grid_cells:
        facts: list[KnowledgeMissionFact] = []
        warnings: list[str] = []
        traversal_cost = 1.0
        cell_kind = str(cell.metadata.get("kind", ""))
        if cell_kind == "restricted_zone":
            facts.append(_knowledge_fact("restricted_area", True, source=source, confidence=0.95))
            facts.append(_knowledge_fact("controlled_airspace", True, source=source, confidence=0.85))
            warnings.append("Restricted or airport-sensitive location supplied in the knowledge context.")
            traversal_cost = 9999.0
        elif cell_kind == "population_sensitive":
            facts.append(_knowledge_fact("people_density", "elevated", source=source, confidence=0.7))
            warnings.append("Population-sensitive site supplied in the knowledge context.")
            traversal_cost = 25.0

        cell_facts.append(
            KnowledgeCellFact(
                cell_id=cell.cell_id,
                facts=facts,
                traversal_cost=traversal_cost,
                warnings=warnings,
            )
        )

    return KnowledgeAgentResponse(
        request_id=request_id,
        mission_id=mission_id,
        mission_level_facts=mission_facts,
        cell_level_facts=cell_facts,
        source=source,
        confidence=0.9,
        verification_status=VerificationStatus.VERIFIED,
        missing_information=(
            knowledge_context.knowledge_reasoning.missing_information if knowledge_context.knowledge_reasoning else []
        ),
        warnings=list(knowledge_context.weather_warning),
    )


def _knowledge_response_fact_strings(knowledge_response: KnowledgeAgentResponse | None) -> list[str]:
    if knowledge_response is None:
        return []

    facts: list[str] = []
    for fact in knowledge_response.mission_level_facts[:6]:
        rendered_value = fact.value
        if isinstance(rendered_value, bool):
            rendered_value = "yes" if rendered_value else "no"
        facts.append(f"Knowledge fact: {fact.category.replace('_', ' ')} = {rendered_value}")
    if knowledge_response.cell_level_facts:
        facts.append(f"Knowledge grid cells evaluated: {len(knowledge_response.cell_level_facts)}")
    return facts


def _build_spatial_constraints(
    *,
    knowledge_context: MissionKnowledgeContext | None,
    knowledge_response: KnowledgeAgentResponse | None,
) -> list[dict[str, object]]:
    constraints: list[dict[str, object]] = []

    if knowledge_context is not None:
        for zone in knowledge_context.restricted_zones:
            constraints.append(
                {
                    "kind": "restricted_zone",
                    "label": zone.name,
                    "types": zone.type,
                    "latitude": zone.latitude,
                    "longitude": zone.longitude,
                    "source": "knowledge_context",
                }
            )
        for zone in knowledge_context.human_zones:
            constraints.append(
                {
                    "kind": "population_sensitive",
                    "label": zone.name,
                    "types": zone.type,
                    "latitude": zone.latitude,
                    "longitude": zone.longitude,
                    "source": "knowledge_context",
                }
            )
        return constraints

    if knowledge_response is None:
        return constraints

    for cell in knowledge_response.cell_level_facts:
        if any(fact.category == "restricted_area" and fact.value is True for fact in cell.facts):
            constraints.append(
                {
                    "kind": "restricted_area",
                    "label": cell.cell_id,
                    "cell_id": cell.cell_id,
                    "warnings": list(cell.warnings),
                    "source": knowledge_response.source,
                }
            )
        elif cell.warnings:
            constraints.append(
                {
                    "kind": "review_cell",
                    "label": cell.cell_id,
                    "cell_id": cell.cell_id,
                    "warnings": list(cell.warnings),
                    "source": knowledge_response.source,
                }
            )
    return constraints


def _serialize_decision(decision, *, knowledge_context_used: bool, knowledge_blocker_count: int, knowledge_refinement_count: int, knowledge_warning_count: int):
    mapped_decision = {
        "APPROVED": "PERMIT",
        "DENIED": "DENY",
        "NEEDS_REVIEW": "INDETERMINATE",
    }.get(str(decision.decision), "INDETERMINATE")
    payload = {
        "decision": mapped_decision,
        "uavguard_status": str(decision.decision),
        "matched_policies": unique_in_order([citation.title for citation in decision.citations]),
        "obligations": list(decision.required_actions),
        "advice": list(decision.review_reasons),
        "warnings": unique_in_order(list(decision.blocking_reasons) + list(decision.review_reasons)),
        "missing_attributes": list(decision.missing_information),
        "citations": [citation.model_dump(mode="json") for citation in decision.citations],
        "explanation": decision.narrative_explanation or decision.concise_summary,
        "confidence": (
            "HIGH"
            if decision.decision in {"APPROVED", "DENIED"} and decision.citations
            else "MEDIUM"
            if decision.citations
            else "LOW"
        ),
        "rule_results": [evaluation.model_dump(mode="json") for evaluation in decision.policy_evaluations],
    }
    mission_score, accuracy_score = compute_grounding_scores(
        preview_decision=payload,
        knowledge_context_used=knowledge_context_used,
        knowledge_blocker_count=knowledge_blocker_count,
        knowledge_refinement_count=knowledge_refinement_count,
        knowledge_warning_count=knowledge_warning_count,
    )
    payload["mission_score"] = mission_score
    payload["accuracy_score"] = accuracy_score
    payload["knowledge_context_used"] = knowledge_context_used
    return payload


def _serialize_simulator_package(simulator_package, *, preview_grid_cells=None):
    if simulator_package is None:
        return None

    status_map = {
        "ALLOWED": ("APPROVED", "PERMIT", False, 1.0),
        "REVIEW": ("NEEDS_REVIEW", "INDETERMINATE", False, 25.0),
        "NO_FLY": ("DENIED", "DENY", True, 9999.0),
    }
    cells = []
    no_fly_zone_cell_ids: list[str] = []
    allowed_cell_ids: list[str] = []
    review_cell_ids: list[str] = []
    cell_metadata_by_id = {
        cell.cell_id: dict(cell.metadata)
        for cell in (preview_grid_cells or [])
    }

    for cell in simulator_package.grid_cells:
        uavguard_status, policy_decision, blocked, cost = status_map.get(
            cell.status,
            ("NEEDS_REVIEW", "INDETERMINATE", False, cell.traversal_cost),
        )
        if blocked:
            no_fly_zone_cell_ids.append(cell.cell_id)
        elif uavguard_status == "APPROVED":
            allowed_cell_ids.append(cell.cell_id)
        else:
            review_cell_ids.append(cell.cell_id)

        cells.append(
            {
                "cell_id": cell.cell_id,
                "blocked": blocked,
                "cost": cell.traversal_cost or cost,
                "policy_decision": policy_decision,
                "uavguard_status": uavguard_status,
                "warnings": list(cell.reasons),
                "missing_attributes": [],
                "citations": [citation.model_dump(mode="json") for citation in cell.citations],
                "explanation": cell.reasons[0] if cell.reasons else "",
                "metadata": {
                    **cell_metadata_by_id.get(cell.cell_id, {}),
                    "triggered_rule_ids": list(cell.triggered_rule_ids),
                },
            }
        )

    simulator_recommendation = {
        "APPROVED": "PROCEED",
        "DENIED": "BLOCK",
        "NEEDS_REVIEW": "REVIEW",
    }.get(str(simulator_package.overall_decision), "REVIEW")

    return {
        "base_request_decision": {"uavguard_status": str(simulator_package.overall_decision)},
        "simulator_recommendation": simulator_recommendation,
        "total_cells": len(cells),
        "no_fly_zone_cell_ids": no_fly_zone_cell_ids,
        "allowed_cell_ids": allowed_cell_ids,
        "review_cell_ids": review_cell_ids,
        "cells": cells,
    }


class PolicyEnforcementPoint:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repository = PolicyRepository(settings)
        self.drone_catalog = DroneCatalogRepository(settings)
        self.pdp = PolicyDecisionPoint(settings, self.repository)
        self.shared_evaluator = SharedMissionEvaluator(
            settings=settings,
            knowledge_client=create_knowledge_agent_client(settings),
            llm_provider=create_llm_provider(settings),
        )

    def _ensure_policy_index(self) -> None:
        if self.repository.has_documents() and not self.repository.has_index():
            self.repository.ingest()

    def ingest_policies(self):
        return self.repository.ingest()

    def evaluate_request(self, policy_request: PolicyRequest):
        self._ensure_policy_index()
        enriched_request, _, catalog_warnings = self.drone_catalog.enrich_request(policy_request)
        decision = self.pdp.evaluate(enriched_request)
        if not catalog_warnings:
            return decision
        return decision.model_copy(update={"warnings": unique_in_order(list(decision.warnings) + catalog_warnings)})

    def assist_request(self, assist_request: PolicyAssistRequest):
        self._ensure_policy_index()
        enriched_request, drone_profile, catalog_warnings = self.drone_catalog.enrich_request(
            assist_request.policy_request
        )
        missing_attributes = evaluate_request_attributes(enriched_request).missing_attributes
        preview_decision = None
        if assist_request.include_decision_preview:
            preview_decision = self.evaluate_request(enriched_request).model_dump()

        return build_assist_response(
            enriched_request=enriched_request,
            drone_profile=drone_profile,
            catalog_warnings=catalog_warnings,
            missing_attributes=missing_attributes,
            preview_decision=preview_decision,
        )

    def _build_chat_simulator_grid_preview(self, *, base_request: PolicyRequest, grid_cells, base_request_decision=None):
        resolved_base_decision = base_request_decision or self.evaluate_request(base_request)
        cell_decisions = []
        for cell in grid_cells:
            cell_request = merge_policy_request_with_cell(base_request, cell)
            cell_decision = self.evaluate_request(cell_request)
            cell_decisions.append(build_grid_cell_decision(cell, cell_decision))
        return build_grid_response(resolved_base_decision, cell_decisions).model_dump(mode="json")

    def chat_request(self, chat_request: PolicyChatRequest):
        self._ensure_policy_index()
        knowledge_merge = merge_knowledge_context(
            current_request=chat_request.policy_request,
            knowledge_context=chat_request.knowledge_context,
        )
        extraction = extract_policy_chat_request(
            message=chat_request.message,
            current_request=knowledge_merge.updated_request,
            drone_catalog=self.drone_catalog,
        )
        missing_attributes = evaluate_request_attributes(extraction.updated_request).missing_attributes
        preview_grid_cells = build_preview_grid_cells(
            policy_request=extraction.updated_request,
            knowledge_context=chat_request.knowledge_context,
        )
        chat_mission = build_chat_mission(mission_id="chat-mission", policy_request=extraction.updated_request)
        chat_drone = build_chat_drone(mission=chat_mission, policy_request=extraction.updated_request)
        chat_profile = build_chat_profile(mission=chat_mission, policy_request=extraction.updated_request)
        grid_cell_payloads = [cell.model_dump(mode="json", exclude_none=True) for cell in preview_grid_cells]
        knowledge_request_model = build_knowledge_request(
            mission=chat_mission,
            grid_cells=grid_cell_payloads,
            drone=chat_drone,
        )
        supplied_knowledge_response = None
        supplied_knowledge_payload = None
        if chat_request.knowledge_context is not None:
            supplied_knowledge_response = _normalize_supplied_knowledge_response(
                knowledge_context=chat_request.knowledge_context,
                mission_id=knowledge_request_model.mission_id,
                request_id=knowledge_request_model.request_id,
                grid_cells=preview_grid_cells,
            )
            supplied_knowledge_payload = chat_request.knowledge_context.model_dump(mode="json")

        shared_result = self.shared_evaluator.evaluate(
            mission=chat_mission,
            profile=chat_profile,
            drone=chat_drone,
            missing_fields=missing_attributes,
            grid_cells=grid_cell_payloads,
            knowledge_request=knowledge_request_model,
            knowledge_response_override=supplied_knowledge_response,
            knowledge_response_payload=supplied_knowledge_payload,
            knowledge_source_override=PolicyKnowledgeSource.SUPPLIED if supplied_knowledge_response else None,
        )

        knowledge_warnings = unique_in_order(list(knowledge_merge.warnings))
        knowledge_gaps = list(knowledge_merge.knowledge_gaps)
        knowledge_blocking_questions = list(knowledge_merge.blocking_questions)
        knowledge_follow_up_questions = list(knowledge_merge.refinement_questions)
        knowledge_verified_facts = list(knowledge_merge.verified_facts)
        if chat_request.knowledge_context is None and shared_result.knowledge_response is not None:
            inferred_gaps, inferred_blocking, inferred_refinement = summarize_missing_information(
                list(shared_result.knowledge_response.missing_information)
            )
            knowledge_warnings = unique_in_order(knowledge_warnings + list(shared_result.knowledge_response.warnings))
            knowledge_gaps = unique_in_order(knowledge_gaps + inferred_gaps)
            knowledge_blocking_questions = unique_in_order(knowledge_blocking_questions + inferred_blocking)
            knowledge_follow_up_questions = unique_in_order(knowledge_follow_up_questions + inferred_refinement)
            knowledge_verified_facts = unique_in_order(
                knowledge_verified_facts + _knowledge_response_fact_strings(shared_result.knowledge_response)
            )

        preview_decision = _serialize_decision(
            shared_result.decision,
            knowledge_context_used=chat_request.knowledge_context is not None or shared_result.knowledge_response is not None,
            knowledge_blocker_count=len(knowledge_blocking_questions),
            knowledge_refinement_count=len(knowledge_follow_up_questions),
            knowledge_warning_count=len(knowledge_warnings),
        )
        simulator_grid_preview = _serialize_simulator_package(
            shared_result.simulator_package,
            preview_grid_cells=preview_grid_cells,
        )
        verified_mission_context = (
            chat_request.knowledge_context.model_dump(mode="json")
            if chat_request.knowledge_context is not None
            else shared_result.knowledge_response_payload
        )
        spatial_constraints = _build_spatial_constraints(
            knowledge_context=chat_request.knowledge_context,
            knowledge_response=shared_result.knowledge_response,
        )

        return build_policy_chat_response(
            settings=self.settings,
            message=chat_request.message,
            extracted_request=extraction.updated_request,
            extracted_fields=unique_in_order(knowledge_merge.extracted_fields + extraction.extracted_fields),
            drone_profile=extraction.drone_profile,
            catalog_warnings=extraction.catalog_warnings,
            knowledge_context_used=chat_request.knowledge_context is not None or shared_result.knowledge_response is not None,
            knowledge_verified_facts=knowledge_verified_facts,
            knowledge_warnings=knowledge_warnings,
            knowledge_gaps=knowledge_gaps,
            knowledge_follow_up_questions=knowledge_follow_up_questions,
            knowledge_blocking_questions=knowledge_blocking_questions,
            follow_up_acknowledgement=extraction.follow_up_acknowledgement,
            preview_decision=preview_decision,
            evaluation_stage=shared_result.evaluation_stage,
            knowledge_agent_called=shared_result.knowledge_agent_called,
            knowledge_source=shared_result.knowledge_source,
            verified_mission_context=verified_mission_context,
            knowledge_request=shared_result.knowledge_request.model_dump(mode="json")
            if shared_result.knowledge_request
            else None,
            knowledge_response=shared_result.knowledge_response_payload,
            spatial_constraints=spatial_constraints,
            simulator_package=shared_result.simulator_package.model_dump(mode="json")
            if shared_result.simulator_package
            else None,
            errors=shared_result.errors,
            knowledge_request_preview=shared_result.knowledge_request.model_dump(mode="json")
            if shared_result.knowledge_request
            else None,
            simulator_grid_preview=simulator_grid_preview,
        )

    def evaluate_grid(self, grid_request: PolicyGridRequest):
        self._ensure_policy_index()
        enriched_base_request, _, _ = self.drone_catalog.enrich_request(grid_request.base_request)
        base_request_decision = self.evaluate_request(enriched_base_request)

        cell_decisions = []
        for cell in grid_request.grid_cells:
            cell_request = merge_policy_request_with_cell(enriched_base_request, cell)
            cell_decision = self.evaluate_request(cell_request)
            cell_decisions.append(build_grid_cell_decision(cell, cell_decision))

        return build_grid_response(base_request_decision, cell_decisions)

    def search_policies(self, query: str, top_k: int | None = None):
        self._ensure_policy_index()
        return self.repository.search(query=query, top_k=top_k or self.settings.retrieval_top_k)

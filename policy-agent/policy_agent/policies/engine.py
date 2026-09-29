from __future__ import annotations

from dataclasses import dataclass

from policy_agent.db.models import DroneProfile, UserPolicyProfile
from policy_agent.policies.retrieval import PolicyRetrievalFacade
from policy_agent.policies.rules import RuleContext, build_default_rules
from policy_agent.schemas.common import DecisionStatus, PolicyEvaluationResult
from policy_agent.schemas.knowledge import KnowledgeAgentResponse
from policy_agent.schemas.mission import MissionDecision, MissionDetailsRead, SimulatorGridCell, SimulatorPolicyPackage
from policy_agent.schemas.policy import PolicyEvaluation
from policy_agent.utils.datetime_utils import utcnow


def _unique_citations(evaluations: list[PolicyEvaluation]):
    seen: set[str] = set()
    citations = []
    for evaluation in evaluations:
        for citation in evaluation.citations:
            if citation.citation_id in seen:
                continue
            seen.add(citation.citation_id)
            citations.append(citation)
    return citations


@dataclass(slots=True)
class DecisionAggregation:
    decision: DecisionStatus
    blocking_reasons: list[str]
    review_reasons: list[str]
    missing_information: list[str]
    required_actions: list[str]


class DeterministicPolicyEngine:
    def __init__(self, *, policy_version: str, retriever: PolicyRetrievalFacade | None = None):
        self.policy_version = policy_version
        self.retriever = retriever or PolicyRetrievalFacade()
        self.rules = build_default_rules()

    def evaluate(
        self,
        *,
        mission: MissionDetailsRead,
        profile: UserPolicyProfile | None,
        drone: DroneProfile | None,
        knowledge_response: KnowledgeAgentResponse | None,
    ) -> MissionDecision:
        evaluations: list[PolicyEvaluation] = []
        for rule in self.rules:
            citations = self.retriever.resolve_citations(
                [
                    record.citation_id
                    for record in self.retriever.retrieve(
                        query=f"{rule.rule_name} {' '.join(rule.query_tags)}",
                        tags=list(rule.query_tags),
                        top_k=2,
                    )
                ]
            )
            evaluation = rule.evaluate(
                RuleContext(
                    mission=mission,
                    profile=profile,
                    drone=drone,
                    knowledge_response=knowledge_response,
                ),
                citations,
            )
            evaluations.append(evaluation)

        aggregation = self._aggregate(evaluations)
        return MissionDecision(
            mission_id=mission.mission_id,
            decision=aggregation.decision,
            concise_summary=self._build_summary(aggregation),
            policy_evaluations=evaluations,
            blocking_reasons=aggregation.blocking_reasons,
            review_reasons=aggregation.review_reasons,
            missing_information=aggregation.missing_information,
            required_actions=aggregation.required_actions,
            citations=_unique_citations(evaluations),
            evaluation_timestamp=utcnow(),
            policy_version=self.policy_version,
        )

    def build_simulator_package(
        self,
        *,
        mission: MissionDetailsRead,
        profile: UserPolicyProfile | None,
        drone: DroneProfile | None,
        knowledge_response: KnowledgeAgentResponse | None,
        overall_decision: MissionDecision,
        no_fly_cost: float = 9999.0,
        review_cost: float = 25.0,
        allowed_cost: float = 1.0,
    ) -> SimulatorPolicyPackage:
        grid_cells: list[SimulatorGridCell] = []

        for cell_fact in knowledge_response.cell_level_facts if knowledge_response else []:
            cell_evaluations: list[PolicyEvaluation] = []
            for rule in self.rules:
                citations = self.retriever.resolve_citations(
                    [
                        record.citation_id
                        for record in self.retriever.retrieve(
                            query=f"{rule.rule_name} {' '.join(rule.query_tags)}",
                            tags=list(rule.query_tags),
                            top_k=2,
                        )
                    ]
                )
                cell_evaluations.append(
                    rule.evaluate(
                        RuleContext(
                            mission=mission,
                            profile=profile,
                            drone=drone,
                            knowledge_response=knowledge_response,
                            cell_fact=cell_fact,
                        ),
                        citations,
                    )
                )

            aggregation = self._aggregate(cell_evaluations)
            if any(fact.category == "restricted_area" and fact.value is True for fact in cell_fact.facts):
                cell_status = "NO_FLY"
                traversal_cost = no_fly_cost
                rule_ids = [evaluation.rule_id for evaluation in cell_evaluations if evaluation.applicability]
                reasons = ["The Knowledge Agent marked this cell as geographically restricted."]
            elif aggregation.decision is DecisionStatus.DENIED:
                cell_status = "NO_FLY"
                traversal_cost = no_fly_cost
                rule_ids = [
                    evaluation.rule_id
                    for evaluation in cell_evaluations
                    if evaluation.result in {PolicyEvaluationResult.VIOLATED, PolicyEvaluationResult.WAIVER_REQUIRED}
                ]
                reasons = aggregation.blocking_reasons
            elif aggregation.decision is DecisionStatus.NEEDS_REVIEW:
                cell_status = "REVIEW"
                traversal_cost = review_cost
                rule_ids = [
                    evaluation.rule_id
                    for evaluation in cell_evaluations
                    if evaluation.result
                    in {
                        PolicyEvaluationResult.UNKNOWN,
                        PolicyEvaluationResult.AUTHORIZATION_REQUIRED,
                    }
                ]
                reasons = aggregation.review_reasons or aggregation.missing_information
            else:
                cell_status = "ALLOWED"
                traversal_cost = allowed_cost
                rule_ids = [
                    evaluation.rule_id
                    for evaluation in cell_evaluations
                    if evaluation.result is PolicyEvaluationResult.SATISFIED
                ]
                reasons = ["Applicable policy checks were satisfied for this grid cell."]

            grid_cells.append(
                SimulatorGridCell(
                    cell_id=cell_fact.cell_id,
                    status=cell_status,
                    traversal_cost=traversal_cost,
                    triggered_rule_ids=rule_ids,
                    reasons=reasons,
                    citations=_unique_citations(cell_evaluations),
                )
            )

        if not grid_cells:
            default_status = "ALLOWED" if overall_decision.decision is DecisionStatus.APPROVED else "REVIEW"
            if overall_decision.decision is DecisionStatus.DENIED:
                default_status = "NO_FLY"
            grid_cells.append(
                SimulatorGridCell(
                    cell_id="mission-default-cell",
                    status=default_status,
                    traversal_cost=allowed_cost if default_status == "ALLOWED" else review_cost,
                    triggered_rule_ids=[
                        evaluation.rule_id
                        for evaluation in overall_decision.policy_evaluations
                        if evaluation.applicability
                    ],
                    reasons=[overall_decision.concise_summary],
                    citations=overall_decision.citations,
                )
            )

        return SimulatorPolicyPackage(
            mission_id=mission.mission_id,
            grid_version="knowledge-agent-v1",
            overall_decision=overall_decision.decision,
            generated_timestamp=utcnow(),
            policy_version=self.policy_version,
            grid_cells=grid_cells,
        )

    def _aggregate(self, evaluations: list[PolicyEvaluation]) -> DecisionAggregation:
        blocking_reasons = [
            evaluation.reason
            for evaluation in evaluations
            if evaluation.result == PolicyEvaluationResult.VIOLATED and evaluation.severity.value == "blocking"
        ]
        waiver_reasons = [
            evaluation.reason
            for evaluation in evaluations
            if evaluation.result == PolicyEvaluationResult.WAIVER_REQUIRED
        ]
        review_reasons = [
            evaluation.reason
            for evaluation in evaluations
            if evaluation.result == PolicyEvaluationResult.AUTHORIZATION_REQUIRED
        ]
        missing_information = [
            evaluation.reason for evaluation in evaluations if evaluation.result == PolicyEvaluationResult.UNKNOWN
        ]
        required_actions = []
        for evaluation in evaluations:
            required_actions.extend(evaluation.required_conditions)

        if blocking_reasons or waiver_reasons:
            return DecisionAggregation(
                decision=DecisionStatus.DENIED,
                blocking_reasons=blocking_reasons + waiver_reasons,
                review_reasons=review_reasons,
                missing_information=missing_information,
                required_actions=required_actions,
            )
        if review_reasons or missing_information:
            return DecisionAggregation(
                decision=DecisionStatus.NEEDS_REVIEW,
                blocking_reasons=[],
                review_reasons=review_reasons,
                missing_information=missing_information,
                required_actions=required_actions,
            )
        return DecisionAggregation(
            decision=DecisionStatus.APPROVED,
            blocking_reasons=[],
            review_reasons=[],
            missing_information=[],
            required_actions=required_actions,
        )

    def _build_summary(self, aggregation: DecisionAggregation) -> str:
        if aggregation.decision is DecisionStatus.APPROVED:
            return "The currently verified mission details satisfy the deterministic policy checks that apply."
        if aggregation.decision is DecisionStatus.DENIED:
            return aggregation.blocking_reasons[0]
        if aggregation.review_reasons:
            return aggregation.review_reasons[0]
        return aggregation.missing_information[0]

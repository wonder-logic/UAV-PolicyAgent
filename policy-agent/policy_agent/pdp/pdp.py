from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.config import Settings
from policy_agent.evaluation.hybrid_evaluator import HybridEvaluator
from policy_agent.evaluation.part107_rules import apply_part107_hard_rules
from policy_agent.evaluation.rule_evaluator import evaluate_request_attributes
from policy_agent.pap.policy_repository import PolicyRepository
from policy_agent.pdp.advice import build_advice
from policy_agent.pdp.obligations import build_obligations
from policy_agent.pdp.safeguards import apply_safeguards
from policy_agent.retrieval.retriever import PolicyRetriever
from policy_agent.utils.json_utils import unique_in_order


class PolicyDecisionPoint:
    def __init__(self, settings: Settings, repository: PolicyRepository):
        self.settings = settings
        self.repository = repository
        self.retriever = PolicyRetriever(repository.vector_store, default_top_k=settings.retrieval_top_k)
        self.hybrid_evaluator = HybridEvaluator(settings)

    def evaluate(self, policy_request: PolicyRequest):
        if self.repository.has_documents() and not self.repository.has_index():
            self.repository.ingest()

        retrieved_chunks = self.retriever.retrieve(policy_request, top_k=self.settings.retrieval_top_k)
        rule_evaluation = evaluate_request_attributes(policy_request)
        candidate_payload, contradictory = self.hybrid_evaluator.evaluate(
            policy_request=policy_request,
            retrieved_chunks=retrieved_chunks,
            missing_attributes=rule_evaluation.missing_attributes,
        )
        decision = apply_safeguards(
            candidate_payload=candidate_payload,
            retrieved_chunks=retrieved_chunks,
            known_missing_attributes=rule_evaluation.missing_attributes,
            contradictory_policy=contradictory,
        )
        decision = apply_part107_hard_rules(policy_request, decision)

        obligations = build_obligations(policy_request, decision.missing_attributes, retrieved_chunks)
        advice = build_advice(policy_request, decision, retrieved_chunks)
        warnings = unique_in_order(list(decision.warnings) + rule_evaluation.warnings)

        return decision.model_copy(
            update={
                "obligations": unique_in_order(list(decision.obligations) + obligations),
                "advice": unique_in_order(list(decision.advice) + advice),
                "warnings": warnings,
                "matched_policies": unique_in_order(decision.matched_policies),
                "missing_attributes": unique_in_order(decision.missing_attributes),
            }
        )

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from policy_agent.schemas.common import PolicyCitation, PolicyEvaluationResult, PolicyRuleSeverity


class PolicyEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    applicability: bool
    result: PolicyEvaluationResult
    severity: PolicyRuleSeverity
    observed_facts: dict[str, object] = Field(default_factory=dict)
    required_conditions: list[str] = Field(default_factory=list)
    reason: str
    citations: list[PolicyCitation] = Field(default_factory=list)

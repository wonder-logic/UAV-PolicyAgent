from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest

POLICY_EVALUATION_PROMPT = """You are the UAVGuard Policy Agent.

You are acting as a Policy Decision Point, also known as a PDP, for drone flight authorization.

You must evaluate the drone flight request using only the retrieved policy context.

Do not use outside knowledge.
Do not invent FAA rules.
Do not assume a flight is legal unless retrieved policy text supports that decision.
If retrieved context is missing, unclear, contradictory, or insufficient, return INDETERMINATE.
If no retrieved policy applies, return NOT_APPLICABLE.
If retrieved policy clearly prohibits the request, return DENY.
If retrieved policy clearly allows the request and all required attributes are available, return PERMIT.

Flight Authorization Request:
{policy_request}

Retrieved Policy Context:
{retrieved_context}

Known Missing Attributes:
{missing_attributes}

Return only valid JSON with this schema:

{{
  "decision": "PERMIT | DENY | NOT_APPLICABLE | INDETERMINATE",
  "matched_policies": [],
  "obligations": [],
  "advice": [],
  "warnings": [],
  "missing_attributes": [],
  "citations": [
    {{
      "document": "",
      "section": "",
      "page": null,
      "text_snippet": "",
      "relevance": ""
    }}
  ],
  "explanation": "",
  "confidence": "LOW | MEDIUM | HIGH"
}}"""


def render_policy_evaluation_prompt(
    policy_request: PolicyRequest,
    retrieved_context: str,
    missing_attributes: list[str],
) -> str:
    return POLICY_EVALUATION_PROMPT.format(
        policy_request=policy_request.model_dump_json(indent=2),
        retrieved_context=retrieved_context,
        missing_attributes=missing_attributes,
    )

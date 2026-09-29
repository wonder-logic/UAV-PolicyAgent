from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from policy_agent.api.schemas import PolicyRequest
from policy_agent.config import Settings
from policy_agent.evaluation.prompts import render_policy_evaluation_prompt
from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.retrieval.citations import render_retrieved_context
from policy_agent.utils.json_utils import extract_first_json_object
from policy_agent.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleLLMEvaluator:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_enabled(self) -> bool:
        return bool(self.settings.llm_base_url and self.settings.llm_api_key and self.settings.llm_model)

    def evaluate(
        self,
        policy_request: PolicyRequest,
        retrieved_chunks: list[RetrievedPolicyChunk],
        missing_attributes: list[str],
    ) -> dict[str, Any] | None:
        if not self.is_enabled:
            return None

        llm_base_url = self.settings.llm_base_url
        llm_api_key = self.settings.llm_api_key
        if llm_base_url is None or llm_api_key is None:
            return None

        prompt = render_policy_evaluation_prompt(
            policy_request=policy_request,
            retrieved_context=render_retrieved_context(retrieved_chunks),
            missing_attributes=missing_attributes,
        )
        endpoint = f"{llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        raw_body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=raw_body,
            headers={
                "Authorization": f"Bearer {llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.settings.llm_timeout_seconds) as response:
                parsed_response = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("LLM evaluation failed, falling back to conservative heuristics: %s", exc)
            return None

        content = parsed_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None
        return extract_first_json_object(content)

from __future__ import annotations

from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.pdp.decision import Citation


def citations_from_chunks(chunks: list[RetrievedPolicyChunk], relevance: str) -> list[Citation]:
    return [
        Citation(
            document=chunk.document,
            section=chunk.section,
            page=chunk.page,
            text_snippet=chunk.text[:280],
            relevance=relevance,
        )
        for chunk in chunks
    ]


def render_retrieved_context(chunks: list[RetrievedPolicyChunk]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        location = f"{chunk.document}"
        if chunk.section:
            location += f" | section: {chunk.section}"
        if chunk.page:
            location += f" | page: {chunk.page}"
        parts.append(f"{location}\n{chunk.text}")
    return "\n\n".join(parts)

from __future__ import annotations

from policy_agent.policies.citations import TRUSTED_CITATIONS
from policy_agent.schemas.common import PolicyCitation


def validate_citations(citations: list[PolicyCitation]) -> list[str]:
    errors: list[str] = []
    for citation in citations:
        trusted = TRUSTED_CITATIONS.get(citation.citation_id)
        if trusted is None:
            errors.append(f"Unknown citation id: {citation.citation_id}")
            continue
        if citation.section != trusted.section:
            errors.append(f"Citation {citation.citation_id} section mismatch.")
        if citation.title != trusted.title:
            errors.append(f"Citation {citation.citation_id} title mismatch.")
    return errors


def explanation_is_supported(*, explanation: str, citations: list[PolicyCitation]) -> bool:
    referenced_sections = {citation.section for citation in citations if citation.section}
    for token in explanation.split():
        cleaned = token.rstrip(".,;:()")
        if cleaned.startswith("107.") or cleaned.startswith("89."):
            if all(cleaned not in (section or "") for section in referenced_sections):
                return False
    return True

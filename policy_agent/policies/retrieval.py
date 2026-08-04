from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from policy_agent.policies.citations import TRUSTED_CITATIONS, citation_from_record
from policy_agent.schemas.common import PolicyCitation


@dataclass(slots=True)
class PolicyRecord:
    citation_id: str
    source: str
    authority: str
    section: str
    title: str
    page: int | None
    effective_date: str | None
    version: str
    source_url: str | None
    excerpt: str
    policy_type: str
    jurisdiction: str
    applicability_tags: list[str] = field(default_factory=list)
    contextual_summary: str = ""


class PolicyIngestionService(Protocol):
    def ingest(self) -> list[PolicyRecord]: ...


class PolicyStore(Protocol):
    def load(self) -> list[PolicyRecord]: ...


class LexicalSearchService(Protocol):
    def search(self, query: str, *, top_k: int = 5) -> list[PolicyRecord]: ...


class VectorSearchService(Protocol):
    def search(self, query: str, *, top_k: int = 5) -> list[PolicyRecord]: ...


class MetadataFilterService(Protocol):
    def filter(self, records: list[PolicyRecord], *, tags: list[str]) -> list[PolicyRecord]: ...


class RankingService(Protocol):
    def rank(self, query: str, records: list[PolicyRecord]) -> list[PolicyRecord]: ...


class CitationResolver(Protocol):
    def resolve(self, citation_id: str) -> PolicyCitation: ...


def _record_from_trusted_citation(citation_id: str) -> PolicyRecord:
    record = TRUSTED_CITATIONS[citation_id]
    return PolicyRecord(
        citation_id=record.citation_id,
        source=record.source,
        authority=record.authority,
        section=record.section,
        title=record.title,
        page=record.page,
        effective_date=record.effective_date.isoformat() if record.effective_date else None,
        version=record.version,
        source_url=record.source_url,
        excerpt=record.excerpt,
        policy_type="federal_regulation",
        jurisdiction="US",
        applicability_tags=list(record.applicability_tags),
        contextual_summary=f"{record.title} applies when the mission touches {', '.join(record.applicability_tags)} constraints.",
    )


class InMemoryPolicyStore:
    def __init__(self) -> None:
        self._records = [_record_from_trusted_citation(citation_id) for citation_id in TRUSTED_CITATIONS]

    def load(self) -> list[PolicyRecord]:
        return list(self._records)

    def resolve(self, citation_id: str) -> PolicyCitation:
        return citation_from_record(TRUSTED_CITATIONS[citation_id])

    def search(self, query: str, *, top_k: int = 5) -> list[PolicyRecord]:
        terms = {term.lower() for term in query.split() if term.strip()}
        scored: list[tuple[int, PolicyRecord]] = []
        for record in self._records:
            haystack = " ".join(
                [
                    record.title,
                    record.section,
                    record.excerpt,
                    " ".join(record.applicability_tags),
                    record.contextual_summary,
                ]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, record))
        ranked = sorted(scored, key=lambda item: item[0], reverse=True)
        return [record for _, record in ranked[:top_k]]

    def filter(self, records: list[PolicyRecord], *, tags: list[str]) -> list[PolicyRecord]:
        if not tags:
            return records
        tag_set = {tag.lower() for tag in tags}
        return [record for record in records if tag_set.intersection(tag.lower() for tag in record.applicability_tags)]

    def rank(self, query: str, records: list[PolicyRecord]) -> list[PolicyRecord]:
        return self.search(query, top_k=max(len(records), 1))


class PolicyRetrievalFacade:
    def __init__(self, store: InMemoryPolicyStore | None = None):
        self.store = store or InMemoryPolicyStore()

    def retrieve(self, *, query: str, tags: list[str] | None = None, top_k: int = 5) -> list[PolicyRecord]:
        lexical_results = self.store.search(query, top_k=top_k * 2)
        filtered = self.store.filter(lexical_results, tags=tags or [])
        if not filtered:
            filtered = lexical_results
        return filtered[:top_k]

    def resolve_citations(self, citation_ids: list[str]) -> list[PolicyCitation]:
        seen: set[str] = set()
        resolved: list[PolicyCitation] = []
        for citation_id in citation_ids:
            if citation_id in seen:
                continue
            seen.add(citation_id)
            resolved.append(self.store.resolve(citation_id))
        return resolved

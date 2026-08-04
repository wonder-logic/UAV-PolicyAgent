from __future__ import annotations

from policy_agent.api.schemas import PolicyRequest
from policy_agent.pap.policy_repository import PolicyRepository
from policy_agent.retrieval.retriever import PolicyRetriever


def test_retriever_returns_relevant_chunks(settings, sample_policy_text):
    (settings.policy_docs_dir / "policy.txt").write_text(sample_policy_text, encoding="utf-8")
    repository = PolicyRepository(settings)
    repository.ingest()

    retriever = PolicyRetriever(repository.vector_store, default_top_k=5)
    request = PolicyRequest(
        operation_type="research",
        night_operation=True,
        remote_id_available=False,
        altitude_ft=450,
    )
    results = retriever.retrieve(request)

    assert results
    assert any("Night Operations" in (result.section or "") or "night" in result.text.lower() for result in results)

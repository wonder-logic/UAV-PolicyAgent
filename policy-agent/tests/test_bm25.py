from __future__ import annotations

from policy_agent.retrieval.bm25 import normalize_scores, score_documents


def test_bm25_prefers_document_with_exact_lexical_match():
    documents = [
        "Night operations require anti-collision lighting visible for at least 3 statute miles.",
        "The groundspeed of the small unmanned aircraft may not exceed 100 miles per hour.",
    ]

    scores = score_documents("anti collision lighting at night", documents)
    normalized = normalize_scores(scores)

    assert scores[0] > scores[1]
    assert normalized[0] == 1.0
    assert normalized[1] < normalized[0]

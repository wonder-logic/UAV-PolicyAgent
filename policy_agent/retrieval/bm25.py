from __future__ import annotations

import math
from collections import Counter

from policy_agent.utils.text_utils import tokenize


def score_documents(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    query_tokens = tokenize(query)
    if not query_tokens or not documents:
        return [0.0 for _ in documents]

    tokenized_documents = [tokenize(document) for document in documents]
    document_lengths = [len(tokens) for tokens in tokenized_documents]
    average_length = sum(document_lengths) / len(document_lengths) if document_lengths else 0.0
    average_length = average_length or 1.0

    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_documents:
        document_frequency.update(set(tokens))

    total_documents = len(tokenized_documents)
    query_frequency = Counter(query_tokens)
    scores: list[float] = []

    for tokens in tokenized_documents:
        token_frequency = Counter(tokens)
        document_length = len(tokens) or 1
        score = 0.0
        for token, query_count in query_frequency.items():
            term_frequency = token_frequency.get(token, 0)
            if term_frequency == 0:
                continue

            doc_frequency = document_frequency.get(token, 0)
            inverse_document_frequency = math.log(1 + (total_documents - doc_frequency + 0.5) / (doc_frequency + 0.5))
            normalization = term_frequency + k1 * (1 - b + b * (document_length / average_length))
            score += inverse_document_frequency * (((k1 + 1) * term_frequency) / normalization) * query_count

        scores.append(score)

    return scores


def normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    if max_score <= 0:
        return [0.0 for _ in scores]
    return [score / max_score for score in scores]

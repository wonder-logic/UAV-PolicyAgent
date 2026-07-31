"""Fuzzy lookup helpers for drone model search."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

try:
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover - exercised in local fallback mode
    fuzz = None
    process = None


def normalize_text(value: str) -> str:
    """Normalize whitespace and casing for lookups."""

    return " ".join(value.lower().strip().split())


def similarity_score(left: str, right: str) -> float:
    """Return a 0-100 similarity score."""

    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if fuzz is not None:
        return float(fuzz.token_sort_ratio(left_norm, right_norm))
    return SequenceMatcher(None, left_norm, right_norm).ratio() * 100


def score_candidates(
    query: str,
    candidates: Iterable[str],
    limit: int = 5,
) -> list[tuple[str, float]]:
    """Return the best candidate matches for a query."""

    candidate_list = list(candidates)
    if not candidate_list:
        return []
    if process is not None:
        matches = process.extract(
            normalize_text(query),
            candidate_list,
            scorer=fuzz.token_sort_ratio,
            limit=limit,
        )
        return [(choice, float(score)) for choice, score, _ in matches]

    scored = [
        (candidate, similarity_score(query, candidate))
        for candidate in candidate_list
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]

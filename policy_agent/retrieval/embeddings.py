from __future__ import annotations

import hashlib
import math

from policy_agent.utils.text_utils import tokenize

EMBEDDING_SIZE = 128


def embed_text(text: str, embedding_size: int = EMBEDDING_SIZE) -> list[float]:
    vector = [0.0] * embedding_size
    tokens = tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(token_hash, 16) % embedding_size
        vector[index] += 1.0

    return normalize_vector(vector)


def normalize_vector(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))

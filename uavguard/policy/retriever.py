"""Chroma-backed policy retrieval with local deterministic embeddings."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

try:
    import chromadb
except ImportError:  # pragma: no cover - declared dependency
    chromadb = None

import numpy as np

from ..api.schemas import PolicyChunk
from ..config.settings import Settings, get_settings


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def embed_text(text: str, dimensions: int = 256) -> list[float]:
    """Create a deterministic local embedding for offline retrieval."""

    vector = np.zeros(dimensions, dtype=np.float32)
    for token in TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        weight = 1.0 + (digest[3] / 255.0)
        vector[index] += sign * weight
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector /= norm
    return vector.astype(float).tolist()


class PolicyRetriever:
    """Persist and query policy chunks in a Chroma collection."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.chroma_path.mkdir(parents=True, exist_ok=True)

    def _client(self) -> Any:
        if chromadb is None:
            raise RuntimeError("chromadb is required for policy retrieval.")
        return chromadb.PersistentClient(path=str(self.settings.chroma_path))

    def _collection(self) -> Any:
        client = self._client()
        return client.get_or_create_collection(name=self.settings.policy_collection)

    def reset(self) -> None:
        client = self._client()
        try:
            client.delete_collection(self.settings.policy_collection)
        except Exception:
            pass
        client.get_or_create_collection(name=self.settings.policy_collection)

    def count(self) -> int:
        return int(self._collection().count())

    def add_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Insert or update policy chunks."""

        if not chunks:
            return 0
        collection = self._collection()
        collection.upsert(
            ids=[chunk["id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[chunk["metadata"] for chunk in chunks],
            embeddings=[embed_text(chunk["text"]) for chunk in chunks],
        )
        return len(chunks)

    def query(self, query: str, limit: int = 4) -> list[PolicyChunk]:
        """Retrieve the top matching chunks for a policy query."""

        collection = self._collection()
        if collection.count() == 0:
            return []
        raw = collection.query(
            query_embeddings=[embed_text(query)],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        chunks: list[PolicyChunk] = []
        for chunk_id, document, metadata, distance in zip(ids, docs, metadatas, distances):
            score = 1.0 / (1.0 + float(distance or 0.0))
            chunks.append(
                PolicyChunk(
                    chunk_id=str(chunk_id),
                    source=str((metadata or {}).get("source", "unknown")),
                    text=document,
                    score=score,
                    metadata=metadata or {},
                )
            )
        return chunks

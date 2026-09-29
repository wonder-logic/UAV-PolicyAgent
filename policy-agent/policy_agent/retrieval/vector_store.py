from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast

from policy_agent.config import Settings
from policy_agent.pap.policy_metadata import PolicyChunk, RetrievedPolicyChunk
from policy_agent.retrieval.bm25 import normalize_scores, score_documents
from policy_agent.retrieval.embeddings import cosine_similarity, embed_text
from policy_agent.utils.json_utils import read_json_file, write_json_file
from policy_agent.utils.logging import get_logger

logger = get_logger(__name__)
VECTOR_WEIGHT = 0.65
BM25_WEIGHT = 0.35


class VectorStore(Protocol):
    def reset(self) -> None: ...

    def upsert(self, chunks: list[PolicyChunk]) -> int: ...

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPolicyChunk]: ...

    def has_index(self) -> bool: ...


class JsonVectorStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path

    def reset(self) -> None:
        write_json_file(self.store_path, {"records": []})

    def has_index(self) -> bool:
        payload = read_json_file(self.store_path, default={"records": []}) or {"records": []}
        return bool(payload.get("records"))

    def upsert(self, chunks: list[PolicyChunk]) -> int:
        records = [{"chunk": chunk.model_dump(), "embedding": embed_text(chunk.text)} for chunk in chunks]
        write_json_file(self.store_path, {"records": records})
        return len(records)

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPolicyChunk]:
        payload = read_json_file(self.store_path, default={"records": []}) or {"records": []}
        records = payload.get("records", [])
        if not records:
            return []

        query_embedding = embed_text(query)
        documents = [str(record["chunk"]["text"]) for record in records]
        bm25_scores = normalize_scores(score_documents(query, documents))
        scored: list[RetrievedPolicyChunk] = []
        for record, bm25_score in zip(records, bm25_scores):
            vector_score = cosine_similarity(query_embedding, record["embedding"])
            score = (VECTOR_WEIGHT * max(vector_score, 0.0)) + (BM25_WEIGHT * bm25_score)
            if score <= 0:
                continue
            scored.append(RetrievedPolicyChunk(**record["chunk"], score=score))

        scored.sort(key=lambda chunk: chunk.score, reverse=True)
        return scored[:top_k]


class ChromaVectorStore:
    def __init__(self, persist_dir: Path):
        import chromadb

        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(name="policy_chunks")

    def reset(self) -> None:
        try:
            self.client.delete_collection("policy_chunks")
        except Exception:  # pragma: no cover - defensive
            pass
        self.collection = self.client.get_or_create_collection(name="policy_chunks")

    def has_index(self) -> bool:
        return self.collection.count() > 0

    def upsert(self, chunks: list[PolicyChunk]) -> int:
        if not chunks:
            self.reset()
            return 0

        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[chunk.model_dump(exclude={"text"}) for chunk in chunks],
            embeddings=cast(Any, [embed_text(chunk.text) for chunk in chunks]),
        )
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPolicyChunk]:
        if self.collection.count() == 0:
            return []

        try:
            get_results = self.collection.get(include=["documents", "metadatas", "embeddings"])
            metadatas = cast(list[dict[str, Any]], get_results.get("metadatas") or [])
            documents = cast(list[str], get_results.get("documents") or [])
            embeddings = cast(list[list[float]], get_results.get("embeddings") or [])
        except Exception:  # pragma: no cover - defensive fallback
            query_results = self.collection.query(
                query_embeddings=cast(Any, [embed_text(query)]),
                n_results=top_k,
            )
            metadatas_nested = cast(list[list[dict[str, Any]]], query_results.get("metadatas") or [[]])
            documents_nested = cast(list[list[str]], query_results.get("documents") or [[]])
            distances_nested = cast(list[list[float]], query_results.get("distances") or [[]])
            fallback_matches: list[RetrievedPolicyChunk] = []
            for metadata, document, distance in zip(
                metadatas_nested[0],
                documents_nested[0],
                distances_nested[0],
            ):
                score = 1.0 / (1.0 + distance)
                fallback_matches.append(RetrievedPolicyChunk(text=document, score=score, **metadata))
            return fallback_matches

        if not metadatas or not documents:
            return []

        query_embedding = embed_text(query)
        bm25_scores = normalize_scores(score_documents(query, documents))
        matches: list[RetrievedPolicyChunk] = []
        for metadata, document, embedding, bm25_score in zip(metadatas, documents, embeddings, bm25_scores):
            vector_score = cosine_similarity(query_embedding, embedding)
            score = (VECTOR_WEIGHT * max(vector_score, 0.0)) + (BM25_WEIGHT * bm25_score)
            if score <= 0:
                continue
            matches.append(RetrievedPolicyChunk(text=document, score=score, **metadata))
        matches.sort(key=lambda chunk: chunk.score, reverse=True)
        return matches[:top_k]


def create_vector_store(settings: Settings) -> VectorStore:
    if settings.vector_backend == "chromadb":
        try:
            return ChromaVectorStore(settings.chroma_dir)
        except Exception as exc:  # pragma: no cover - fallback path
            logger.warning("ChromaDB unavailable, falling back to JSON vector store: %s", exc)
    return JsonVectorStore(settings.vector_store_path)

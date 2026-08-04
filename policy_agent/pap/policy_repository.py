from __future__ import annotations

from policy_agent.config import Settings
from policy_agent.pap.default_policy_docs import builtin_policy_documents
from policy_agent.pap.policy_metadata import PolicyChunk, PolicyIngestionSummary, RetrievedPolicyChunk
from policy_agent.retrieval.chunker import chunk_documents
from policy_agent.retrieval.document_loader import discover_document_sources, load_documents
from policy_agent.retrieval.vector_store import VectorStore, create_vector_store
from policy_agent.utils.json_utils import write_json_file


class PolicyRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.ensure_directories()
        self.vector_store: VectorStore = create_vector_store(settings)

    def _load_policy_documents(self):
        custom_documents = load_documents(self.settings.policy_docs_dir)
        if custom_documents:
            return custom_documents, str(self.settings.policy_docs_dir)
        return builtin_policy_documents(), "builtin://uavguard/part107-baseline"

    def has_documents(self) -> bool:
        return bool(discover_document_sources(self.settings.policy_docs_dir) or builtin_policy_documents())

    def has_index(self) -> bool:
        return self.vector_store.has_index()

    def ingest(self) -> PolicyIngestionSummary:
        documents, source_label = self._load_policy_documents()
        chunks = chunk_documents(documents)
        self.vector_store.reset()
        self.vector_store.upsert(chunks)
        write_json_file(
            self.settings.policy_chunks_path,
            [chunk.model_dump() for chunk in chunks],
        )
        return PolicyIngestionSummary(
            documents_loaded=len(documents),
            chunks_indexed=len(chunks),
            vector_backend=self.settings.vector_backend,
            policy_directory=source_label,
        )

    def search(self, query: str, top_k: int = 5) -> list[RetrievedPolicyChunk]:
        return self.vector_store.search(query, top_k=top_k)

    def index_chunks(self, chunks: list[PolicyChunk]) -> int:
        self.vector_store.reset()
        count = self.vector_store.upsert(chunks)
        write_json_file(
            self.settings.policy_chunks_path,
            [chunk.model_dump() for chunk in chunks],
        )
        return count

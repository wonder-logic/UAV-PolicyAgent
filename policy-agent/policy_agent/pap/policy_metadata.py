from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyDocument(BaseModel):
    document_name: str
    source_path: str
    file_type: str
    content: str
    pages: list[str] = Field(default_factory=list)


class PolicyChunk(BaseModel):
    chunk_id: str
    document: str
    source_path: str
    section: str | None = None
    page: int | None = None
    chunk_index: int
    text: str


class RetrievedPolicyChunk(PolicyChunk):
    score: float = 0.0


class PolicyIngestionSummary(BaseModel):
    documents_loaded: int
    chunks_indexed: int
    vector_backend: str
    policy_directory: str

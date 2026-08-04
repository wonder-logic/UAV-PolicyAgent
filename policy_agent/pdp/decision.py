from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document: str
    section: str | None = None
    page: int | None = None
    text_snippet: str
    relevance: str


class PDPDecision(BaseModel):
    decision: Literal["PERMIT", "DENY", "NOT_APPLICABLE", "INDETERMINATE"]
    uavguard_status: Literal["APPROVED", "DENIED", "NEEDS_REVIEW"]
    matched_policies: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    advice: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    explanation: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"]

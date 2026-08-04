from __future__ import annotations

import re

from policy_agent.pap.policy_metadata import PolicyChunk, PolicyDocument
from policy_agent.utils.text_utils import normalize_whitespace

SECTION_HEADER_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Za-z0-9\s/\-]{2,}:?)$")


def _detect_section_heading(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:3]:
        if SECTION_HEADER_RE.match(line):
            return line.lstrip("#").strip().rstrip(":")
    return None


def _section_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if SECTION_HEADER_RE.match(stripped) and current_block:
            blocks.append("\n".join(current_block).strip())
            current_block = [line]
            continue
        current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block).strip())

    return [block for block in blocks if block.strip()]


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            overlap = current[-chunk_overlap:] if chunk_overlap else ""
            current = f"{overlap}\n\n{paragraph}".strip()
        else:
            start = 0
            while start < len(paragraph):
                end = min(start + chunk_size, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                if end >= len(paragraph):
                    break
                start = max(end - chunk_overlap, start + 1)
            current = ""

    if current:
        chunks.append(current)

    return [normalize_whitespace(chunk) for chunk in chunks if normalize_whitespace(chunk)]


def chunk_document(document: PolicyDocument, chunk_size: int = 900, chunk_overlap: int = 120) -> list[PolicyChunk]:
    raw_chunks: list[PolicyChunk] = []

    if document.pages:
        chunk_index = 0
        for page_number, page_text in enumerate(document.pages, start=1):
            if not page_text.strip():
                continue
            for block in _section_blocks(page_text):
                section = _detect_section_heading(block)
                for text in _split_text(block, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
                    raw_chunks.append(
                        PolicyChunk(
                            chunk_id=f"{document.document_name}:{page_number}:{chunk_index}",
                            document=document.document_name,
                            source_path=document.source_path,
                            section=section,
                            page=page_number,
                            chunk_index=chunk_index,
                            text=text,
                        )
                    )
                    chunk_index += 1
        return raw_chunks

    chunk_index = 0
    for block in _section_blocks(document.content):
        section = _detect_section_heading(block)
        for text in _split_text(block, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            raw_chunks.append(
                PolicyChunk(
                    chunk_id=f"{document.document_name}:na:{chunk_index}",
                    document=document.document_name,
                    source_path=document.source_path,
                    section=section,
                    page=None,
                    chunk_index=chunk_index,
                    text=text,
                )
            )
            chunk_index += 1
    return raw_chunks


def chunk_documents(
    documents: list[PolicyDocument], chunk_size: int = 900, chunk_overlap: int = 120
) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return chunks

"""Policy document ingestion for TXT and PDF sources."""

from __future__ import annotations

from pathlib import Path
import re

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - declared dependency
    PdfReader = None

from ..config.settings import Settings, get_settings
from .retriever import PolicyRetriever


def _read_pdf(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is required to ingest PDF policy documents.")
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())
    return "\n\n".join(page for page in pages if page)


def read_policy_document(path: str | Path) -> str:
    """Read a supported policy file into plain text."""

    resolved_path = Path(path)
    if resolved_path.suffix.lower() == ".pdf":
        return _read_pdf(resolved_path)
    return resolved_path.read_text(encoding="utf-8", errors="ignore")


def chunk_policy_text(text: str, chunk_size: int = 900, overlap_words: int = 80) -> list[str]:
    """Chunk policy text into retrieval-friendly windows."""

    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]).strip())
        if end >= len(words):
            break
        start = max(end - overlap_words, start + 1)
    return [chunk for chunk in chunks if chunk]


def ingest_policy_directory(
    directory: str | Path | None = None,
    settings: Settings | None = None,
) -> int:
    """Rebuild the policy collection from a directory of FAA docs."""

    resolved_settings = settings or get_settings()
    policies_dir = Path(directory) if directory is not None else resolved_settings.faa_docs_dir
    retriever = PolicyRetriever(resolved_settings)
    retriever.reset()

    indexed_chunks: list[dict[str, object]] = []
    supported_paths = sorted(
        path
        for path in policies_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".txt", ".pdf"}
    )
    for path in supported_paths:
        text = read_policy_document(path)
        for index, chunk in enumerate(chunk_policy_text(text), start=1):
            indexed_chunks.append(
                {
                    "id": f"{path.stem}-{index}",
                    "text": chunk,
                    "metadata": {
                        "source": path.name,
                        "path": str(path),
                        "chunk_index": index,
                    },
                }
            )
    return retriever.add_chunks(indexed_chunks)

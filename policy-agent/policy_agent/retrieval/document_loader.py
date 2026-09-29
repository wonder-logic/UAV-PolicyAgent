from __future__ import annotations

from pathlib import Path

from policy_agent.pap.policy_metadata import PolicyDocument
from policy_agent.utils.text_utils import clean_text

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def discover_document_sources(policy_docs_dir: Path) -> list[Path]:
    return sorted(
        path for path in policy_docs_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _load_pdf_document(path: Path) -> PolicyDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(clean_text(page_text))

    content = clean_text("\n\n".join(page for page in pages if page))
    return PolicyDocument(
        document_name=path.name,
        source_path=str(path),
        file_type="pdf",
        content=content,
        pages=pages,
    )


def load_document(path: Path) -> PolicyDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported policy document type: {path.suffix}")

    if suffix == ".pdf":
        return _load_pdf_document(path)

    content = clean_text(path.read_text(encoding="utf-8"))
    return PolicyDocument(
        document_name=path.name,
        source_path=str(path),
        file_type=suffix.lstrip("."),
        content=content,
        pages=[],
    )


def load_documents(policy_docs_dir: Path) -> list[PolicyDocument]:
    return [load_document(path) for path in discover_document_sources(policy_docs_dir)]

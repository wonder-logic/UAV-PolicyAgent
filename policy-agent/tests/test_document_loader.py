from __future__ import annotations

from policy_agent.retrieval.document_loader import load_document


def test_load_txt_policy_document(settings, sample_policy_text):
    policy_path = settings.policy_docs_dir / "policy.txt"
    policy_path.write_text(sample_policy_text, encoding="utf-8")

    document = load_document(policy_path)

    assert document.document_name == "policy.txt"
    assert "Night operations" in document.content


def test_load_pdf_policy_document(settings):
    from tests.conftest import build_pdf_bytes

    pdf_path = settings.policy_docs_dir / "policy.pdf"
    pdf_path.write_bytes(build_pdf_bytes("Night operations require Remote ID."))

    document = load_document(pdf_path)

    assert document.file_type == "pdf"
    assert "Night operations require Remote ID." in document.content

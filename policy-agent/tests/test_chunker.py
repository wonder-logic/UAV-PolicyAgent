from __future__ import annotations

from policy_agent.pap.policy_metadata import PolicyDocument
from policy_agent.retrieval.chunker import chunk_document


def test_chunker_splits_policy_text_into_chunks():
    text = "\n\n".join(
        [
            "# Operations",
            "Night operations are permitted when Remote ID is active and visual line of sight is maintained." * 4,
            "Flights must not exceed 400 feet above ground level." * 4,
        ]
    )
    document = PolicyDocument(
        document_name="policy.txt",
        source_path="policy.txt",
        file_type="txt",
        content=text,
        pages=[],
    )

    chunks = chunk_document(document, chunk_size=180, chunk_overlap=20)

    assert len(chunks) >= 2
    assert all(chunk.text for chunk in chunks)

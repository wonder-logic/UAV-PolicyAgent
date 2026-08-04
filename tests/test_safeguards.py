from __future__ import annotations

from policy_agent.pap.policy_metadata import RetrievedPolicyChunk
from policy_agent.pdp.safeguards import apply_safeguards


def test_safeguards_downgrade_permit_without_citations():
    chunk = RetrievedPolicyChunk(
        chunk_id="demo:0",
        document="demo.txt",
        source_path="demo.txt",
        section="Night Operations",
        page=None,
        chunk_index=0,
        text="Night operations are permitted when Remote ID is active.",
        score=0.8,
    )
    decision = apply_safeguards(
        candidate_payload={
            "decision": "PERMIT",
            "matched_policies": ["demo.txt#Night Operations"],
            "obligations": [],
            "advice": [],
            "warnings": [],
            "missing_attributes": [],
            "citations": [],
            "explanation": "Permit.",
            "confidence": "MEDIUM",
        },
        retrieved_chunks=[chunk],
        known_missing_attributes=[],
    )

    assert decision.decision == "INDETERMINATE"

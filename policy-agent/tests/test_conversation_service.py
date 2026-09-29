from __future__ import annotations

from policy_agent.pep.conversation_service import build_follow_up_questions


def test_build_follow_up_questions_uses_human_readable_language():
    questions = build_follow_up_questions(["operation_type", "visual_line_of_sight"])

    assert questions == [
        "What kind of operation is this: recreational, commercial, research, or public safety?",
        "Will the pilot or visual observer be able to keep the drone directly in sight for the entire mission?",
    ]

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from policy_agent.schemas.mission import MissionDecision, MissionDetailsRead, MissionUpdateExtraction


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: str
    content: str
    created_at: datetime


class MissionChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)


class MissionChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission: MissionDetailsRead
    assistant_message: str
    extraction: MissionUpdateExtraction
    missing_fields: list[str] = Field(default_factory=list)
    next_required_action: str | None = None
    decision_preview: MissionDecision | None = None
    conversation: list[ConversationMessage] = Field(default_factory=list)

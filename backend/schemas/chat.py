from typing import Any, Literal
from datetime import datetime
from pydantic import Field

from .common import APIModel


class ConversationCreateRequest(APIModel):
    dataset_id: str | None = None


class ConversationRenameRequest(APIModel):
    title: str = Field(..., min_length=1, max_length=255)


class MessageCreateRequest(APIModel):
    question: str
    dataset_id: str | None = None


class MessageResponse(APIModel):
    model_config = {"extra": "ignore"}
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    message_type: Literal["question", "answer", "error"]
    content: str
    dataset_id: str | None = None
    created_at: datetime
    result_metadata: dict[str, Any] | None = None
    user_id: str | None = None
    user_name: str | None = None


class ConversationSummary(APIModel):
    model_config = {"extra": "ignore"}
    id: str
    title: str
    dataset_id: str | None = None
    workspace_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse]

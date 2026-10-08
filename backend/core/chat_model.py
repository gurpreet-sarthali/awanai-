"""Chat and conversation models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ConversationRecord:
    id: str
    user_id: str
    dataset_id: str | None
    title: str
    created_at: datetime
    updated_at: datetime
    workspace_id: str | None = None


@dataclass(frozen=True)
class MessageRecord:
    id: str
    conversation_id: str
    role: str
    message_type: str
    content: str
    dataset_id: str | None
    created_at: datetime
    result_metadata: dict[str, Any] | None
    user_id: str | None = None
    user_name: str | None = None

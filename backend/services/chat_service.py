"""Chat and conversation service."""

from __future__ import annotations

from typing import Any

from backend.core.chat_model import ConversationRecord, MessageRecord
from backend.repositories.chat_repository import ChatRepository, ConversationNotFoundError


class ChatServiceError(ValueError):
    pass


class ChatService:
    def __init__(self, repository: ChatRepository) -> None:
        self.repository = repository
        self.repository.ensure_schema()

    def create_conversation(self, user_id: str, title: str, dataset_id: str | None = None) -> ConversationRecord:
        return self.repository.create_conversation(user_id=user_id, title=title, dataset_id=dataset_id)

    def get_conversation_for_user(self, conversation_id: str, user_id: str) -> ConversationRecord:
        try:
            return self.repository.get_conversation_for_user(conversation_id, user_id)
        except ConversationNotFoundError as error:
            raise ChatServiceError("Conversation not found.") from error

    def list_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> list[ConversationRecord]:
        return self.repository.list_conversations(user_id, limit=limit, offset=offset)

    def rename_conversation(self, conversation_id: str, user_id: str, title: str) -> ConversationRecord:
        self.get_conversation_for_user(conversation_id, user_id)
        return self.repository.rename_conversation(conversation_id, title)

    def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        self.get_conversation_for_user(conversation_id, user_id)
        self.repository.delete_conversation(conversation_id)

    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        message_type: str,
        content: str,
        dataset_id: str | None = None,
        result_metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        self.get_conversation_for_user(conversation_id, user_id)
        return self.repository.add_message(
            conversation_id=conversation_id,
            role=role,
            message_type=message_type,
            content=content,
            dataset_id=dataset_id,
            result_metadata=result_metadata,
        )

    def get_messages(self, conversation_id: str, user_id: str, limit: int = 100, offset: int = 0) -> list[MessageRecord]:
        self.get_conversation_for_user(conversation_id, user_id)
        return self.repository.get_messages(conversation_id, limit=limit, offset=offset)

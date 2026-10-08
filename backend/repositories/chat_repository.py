"""Chat repository."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect
from backend.core.chat_model import ConversationRecord, MessageRecord


class ConversationNotFoundError(LookupError):
    pass


class ChatRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        dataset_id TEXT NULL,
                        workspace_id TEXT NULL,
                        title TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT NOT NULL PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        dataset_id TEXT NULL,
                        user_id TEXT NULL,
                        user_name TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        result_metadata TEXT NULL,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    )
                    """
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NULL,
                        title VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        KEY idx_conversations_user (user_id),
                        KEY idx_conversations_updated (updated_at)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        conversation_id VARCHAR(64) NOT NULL,
                        role VARCHAR(32) NOT NULL,
                        message_type VARCHAR(32) NOT NULL,
                        content TEXT NOT NULL,
                        dataset_id VARCHAR(64) NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        result_metadata JSON NULL,
                        KEY idx_messages_conversation (conversation_id),
                        KEY idx_messages_created (created_at),
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    )
                    """
                )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

        # Schema migrations for Phase 18 workspace support
        try:
            connection = connect(self.config)
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                existing_conv_cols = {row[1] for row in cursor.execute("PRAGMA table_info(conversations)").fetchall()}
                if "workspace_id" not in existing_conv_cols:
                    cursor.execute("ALTER TABLE conversations ADD COLUMN workspace_id TEXT NULL")
                existing_msg_cols = {row[1] for row in cursor.execute("PRAGMA table_info(messages)").fetchall()}
                if "user_id" not in existing_msg_cols:
                    cursor.execute("ALTER TABLE messages ADD COLUMN user_id TEXT NULL")
                if "user_name" not in existing_msg_cols:
                    cursor.execute("ALTER TABLE messages ADD COLUMN user_name TEXT NULL")
                connection.commit()
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'conversations' AND COLUMN_NAME = 'workspace_id'
                    """,
                    (self.config.database,),
                )
                if int(cursor.fetchone()[0]) == 0:
                    cursor.execute("ALTER TABLE conversations ADD COLUMN workspace_id VARCHAR(64) NULL AFTER dataset_id")
                    cursor.execute("ALTER TABLE conversations ADD KEY idx_conversations_workspace (workspace_id)")
                    connection.commit()

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'messages' AND COLUMN_NAME = 'user_id'
                    """,
                    (self.config.database,),
                )
                if int(cursor.fetchone()[0]) == 0:
                    cursor.execute("ALTER TABLE messages ADD COLUMN user_id VARCHAR(64) NULL AFTER dataset_id")
                    cursor.execute("ALTER TABLE messages ADD COLUMN user_name VARCHAR(255) NULL AFTER user_id")
                    connection.commit()
            cursor.close()
        except Exception:
            pass
        finally:
            connection.close()

    def create_conversation(self, user_id: str, title: str, dataset_id: str | None = None, workspace_id: str | None = None) -> ConversationRecord:
        conversation_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO conversations (id, user_id, dataset_id, title, workspace_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (conversation_id, user_id, dataset_id, title, workspace_id),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: str) -> ConversationRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise ConversationNotFoundError(conversation_id)
            return _row_to_conversation(row)
        finally:
            connection.close()

    def get_conversation_for_user(self, conversation_id: str, user_id: str) -> ConversationRecord:
        record = self.get_conversation(conversation_id)
        if record.user_id != user_id and not record.workspace_id:
            raise ConversationNotFoundError(conversation_id)
        return record

    def list_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> list[ConversationRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT * FROM conversations
                WHERE user_id = %s AND workspace_id IS NULL
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [_row_to_conversation(row) for row in rows]
        finally:
            connection.close()

    def list_workspace_conversations(self, workspace_id: str, limit: int = 50, offset: int = 0) -> list[ConversationRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT * FROM conversations
                WHERE workspace_id = %s
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (workspace_id, limit, offset),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [_row_to_conversation(row) for row in rows]
        finally:
            connection.close()

    def rename_conversation(self, conversation_id: str, title: str) -> ConversationRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE conversations SET title = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (title, conversation_id),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        return self.get_conversation(conversation_id)

    def delete_conversation(self, conversation_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        message_type: str,
        content: str,
        dataset_id: str | None = None,
        result_metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        user_name: str | None = None,
    ) -> MessageRecord:
        message_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            metadata_json = json.dumps(result_metadata) if result_metadata is not None else None
            cursor.execute(
                """
                INSERT INTO messages (id, conversation_id, role, message_type, content, dataset_id, result_metadata, user_id, user_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (message_id, conversation_id, role, message_type, content, dataset_id, metadata_json, user_id, user_name),
            )
            cursor.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (conversation_id,),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        return self.get_message(message_id)

    def get_message(self, message_id: str) -> MessageRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise LookupError(f"Message {message_id} not found")
            return _row_to_message(row)
        finally:
            connection.close()

    def get_messages(self, conversation_id: str, limit: int = 100, offset: int = 0) -> list[MessageRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                LIMIT %s OFFSET %s
                """,
                (conversation_id, limit, offset),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [_row_to_message(row) for row in rows]
        finally:
            connection.close()


def _row_to_conversation(row: dict[str, Any]) -> ConversationRecord:
    return ConversationRecord(
        id=row["id"],
        user_id=row["user_id"],
        dataset_id=row["dataset_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        workspace_id=row.get("workspace_id"),
    )


def _row_to_message(row: dict[str, Any]) -> MessageRecord:
    metadata = row.get("result_metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = None

    return MessageRecord(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        message_type=row["message_type"],
        content=row["content"],
        dataset_id=row["dataset_id"],
        created_at=row["created_at"],
        result_metadata=metadata,
        user_id=row.get("user_id"),
        user_name=row.get("user_name"),
    )

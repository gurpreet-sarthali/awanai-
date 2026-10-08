"""Workspace and collaboration repository for Phase 18."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect

_log = logging.getLogger(__name__)


class WorkspaceNotFoundError(LookupError):
    pass


class WorkspaceAccessError(PermissionError):
    pass


class WorkspaceConflictError(ValueError):
    pass


@dataclass(frozen=True, kw_only=True)
class WorkspaceRecord:
    id: str
    name: str
    description: str | None
    owner_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class WorkspaceMemberRecord:
    id: str
    workspace_id: str
    user_id: str
    role: str
    joined_at: datetime
    user_email: str | None = None
    user_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class WorkspaceInvitationRecord:
    id: str
    workspace_id: str
    inviter_id: str
    invitee_email: str
    role: str
    token_hash: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    workspace_name: str | None = None
    inviter_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class WorkspaceDatasetRecord:
    id: str
    workspace_id: str
    dataset_id: str
    shared_by_user_id: str
    created_at: datetime
    dataset_name: str | None = None
    shared_by_user_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class WorkspaceAnalysisResultRecord:
    id: str
    workspace_id: str
    dataset_id: str
    user_id: str
    question: str
    answer: str
    metrics_json: str | None
    chart_json: str | None
    insights_json: str | None
    created_at: datetime
    user_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class AnalysisCommentRecord:
    id: str
    result_id: str
    user_id: str
    comment_text: str
    created_at: datetime
    user_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class WorkspaceActivityLogRecord:
    id: str
    workspace_id: str
    user_id: str | None
    event_type: str
    metadata_json: str | None
    created_at: datetime
    user_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class NotificationRecord:
    id: str
    user_id: str
    title: str
    message: str
    is_read: bool
    created_at: datetime


class WorkspaceRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def _is_sqlite(self) -> bool:
        return self.config.uses_sqlite

    def _table_exists(self, table_name: str) -> bool:
        connection = connect(self.config)
        try:
            if self._is_sqlite():
                cursor = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                    (table_name,),
                )
                return cursor.fetchone() is not None
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (self.config.database, table_name),
            )
            return int(cursor.fetchone()[0]) > 0
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        """Create tables for workspaces, members, invitations, shared datasets, analysis results, activity logs, and notifications."""
        try:
            connection = connect(self.config)
        except Exception as err:
            _log.warning("WorkspaceRepository: DB connection failed in ensure_schema: %s", err)
            return

        try:
            cursor = connection.cursor()
            if self._is_sqlite():
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspaces (
                        id TEXT NOT NULL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NULL,
                        owner_id TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_members (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'analyst',
                        joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (workspace_id, user_id)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_invitations (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        inviter_id TEXT NOT NULL,
                        invitee_email TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'analyst',
                        token_hash TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        accepted_at TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_datasets (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL,
                        shared_by_user_id TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (workspace_id, dataset_id)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_analysis_results (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        metrics_json TEXT NULL,
                        chart_json TEXT NULL,
                        insights_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_comments (
                        id TEXT NOT NULL PRIMARY KEY,
                        result_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        comment_text TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_activity_logs (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NULL,
                        event_type TEXT NOT NULL,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_notifications (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        is_read INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                for index_sql in (
                    "CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_id)",
                    "CREATE INDEX IF NOT EXISTS idx_wm_user ON workspace_members(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_wm_role ON workspace_members(role)",
                    "CREATE INDEX IF NOT EXISTS idx_wi_email ON workspace_invitations(invitee_email)",
                    "CREATE INDEX IF NOT EXISTS idx_wi_hash ON workspace_invitations(token_hash)",
                    "CREATE INDEX IF NOT EXISTS idx_wi_workspace ON workspace_invitations(workspace_id)",
                    "CREATE INDEX IF NOT EXISTS idx_wd_dataset ON workspace_datasets(dataset_id)",
                    "CREATE INDEX IF NOT EXISTS idx_wd_workspace ON workspace_datasets(workspace_id)",
                    "CREATE INDEX IF NOT EXISTS idx_war_workspace ON workspace_analysis_results(workspace_id)",
                    "CREATE INDEX IF NOT EXISTS idx_war_dataset ON workspace_analysis_results(dataset_id)",
                    "CREATE INDEX IF NOT EXISTS idx_ac_result ON analysis_comments(result_id)",
                    "CREATE INDEX IF NOT EXISTS idx_wal_workspace ON workspace_activity_logs(workspace_id)",
                    "CREATE INDEX IF NOT EXISTS idx_wal_created ON workspace_activity_logs(created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_un_user ON user_notifications(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_un_read ON user_notifications(is_read)",
                ):
                    cursor.execute(index_sql)
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspaces (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT NULL,
                        owner_id VARCHAR(64) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        KEY idx_workspaces_owner (owner_id)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_members (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NOT NULL,
                        role VARCHAR(32) NOT NULL DEFAULT 'analyst',
                        joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uq_workspace_user (workspace_id, user_id),
                        KEY idx_wm_user (user_id),
                        KEY idx_wm_role (role)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_invitations (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        inviter_id VARCHAR(64) NOT NULL,
                        invitee_email VARCHAR(255) NOT NULL,
                        role VARCHAR(32) NOT NULL DEFAULT 'analyst',
                        token_hash VARCHAR(128) NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        accepted_at TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_wi_email (invitee_email),
                        KEY idx_wi_hash (token_hash),
                        KEY idx_wi_workspace (workspace_id)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_datasets (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL,
                        shared_by_user_id VARCHAR(64) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uq_workspace_dataset (workspace_id, dataset_id),
                        KEY idx_wd_dataset (dataset_id),
                        KEY idx_wd_workspace (workspace_id)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_analysis_results (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NOT NULL,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        metrics_json TEXT NULL,
                        chart_json TEXT NULL,
                        insights_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_war_workspace (workspace_id),
                        KEY idx_war_dataset (dataset_id)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_comments (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        result_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NOT NULL,
                        comment_text TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_ac_result (result_id)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_activity_logs (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NULL,
                        event_type VARCHAR(64) NOT NULL,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_wal_workspace (workspace_id),
                        KEY idx_wal_created (created_at)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_notifications (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        message TEXT NOT NULL,
                        is_read TINYINT(1) NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_un_user (user_id),
                        KEY idx_un_read (is_read)
                    )
                    """
                )

            connection.commit()
            cursor.close()
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # WORKSPACE CRUD
    # -------------------------------------------------------------------------

    def create_workspace(self, name: str, owner_id: str, description: str | None = None) -> WorkspaceRecord:
        ws_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO workspaces (id, name, description, owner_id)
                VALUES (%s, %s, %s, %s)
                """,
                (ws_id, name, description, owner_id),
            )
            # Owner automatically added as workspace member with role 'owner'
            mem_id = str(uuid4())
            cursor.execute(
                """
                INSERT INTO workspace_members (id, workspace_id, user_id, role)
                VALUES (%s, %s, %s, %s)
                """,
                (mem_id, ws_id, owner_id, "owner"),
            )
            connection.commit()
            cursor.close()
            return self.get_workspace(ws_id)
        finally:
            connection.close()

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, name, description, owner_id, created_at, updated_at
                FROM workspaces
                WHERE id = %s
                """,
                (workspace_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise WorkspaceNotFoundError(f"Workspace `{workspace_id}` does not exist.")
            return WorkspaceRecord(
                id=str(row[0]),
                name=str(row[1]),
                description=str(row[2]) if row[2] is not None else None,
                owner_id=str(row[3]),
                created_at=row[4],
                updated_at=row[5],
            )
        finally:
            connection.close()

    def list_workspaces_for_user(self, user_id: str) -> list[WorkspaceRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT w.id, w.name, w.description, w.owner_id, w.created_at, w.updated_at
                FROM workspaces w
                JOIN workspace_members wm ON w.id = wm.workspace_id
                WHERE wm.user_id = %s
                ORDER BY w.updated_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                WorkspaceRecord(
                    id=str(r[0]),
                    name=str(r[1]),
                    description=str(r[2]) if r[2] is not None else None,
                    owner_id=str(r[3]),
                    created_at=r[4],
                    updated_at=r[5],
                )
                for r in rows
            ]
        finally:
            connection.close()

    def update_workspace(self, workspace_id: str, name: str | None = None, description: str | None = None) -> WorkspaceRecord:
        ws = self.get_workspace(workspace_id)
        new_name = name if name is not None else ws.name
        new_desc = description if description is not None else ws.description
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE workspaces
                SET name = %s, description = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (new_name, new_desc, workspace_id),
            )
            connection.commit()
            cursor.close()
            return self.get_workspace(workspace_id)
        finally:
            connection.close()

    def delete_workspace(self, workspace_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM workspace_members WHERE workspace_id = %s", (workspace_id,))
            cursor.execute("DELETE FROM workspace_invitations WHERE workspace_id = %s", (workspace_id,))
            cursor.execute("DELETE FROM workspace_datasets WHERE workspace_id = %s", (workspace_id,))
            cursor.execute("DELETE FROM workspace_analysis_results WHERE workspace_id = %s", (workspace_id,))
            cursor.execute("DELETE FROM workspace_activity_logs WHERE workspace_id = %s", (workspace_id,))
            cursor.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # MEMBERS & ROLES
    # -------------------------------------------------------------------------

    def get_member(self, workspace_id: str, user_id: str) -> WorkspaceMemberRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, u.email, u.name
                    FROM workspace_members wm
                    LEFT JOIN users u ON wm.user_id = u.id
                    WHERE wm.workspace_id = %s AND wm.user_id = %s
                    """,
                    (workspace_id, user_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, NULL AS email, NULL AS name
                    FROM workspace_members wm
                    WHERE wm.workspace_id = ? AND wm.user_id = ?
                    """,
                    (workspace_id, user_id),
                )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return WorkspaceMemberRecord(
                id=str(row[0]),
                workspace_id=str(row[1]),
                user_id=str(row[2]),
                role=str(row[3]),
                joined_at=row[4],
                user_email=str(row[5]) if row[5] else None,
                user_name=str(row[6]) if row[6] else None,
            )
        finally:
            connection.close()

    def list_members(self, workspace_id: str) -> list[WorkspaceMemberRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, u.email, u.name
                    FROM workspace_members wm
                    LEFT JOIN users u ON wm.user_id = u.id
                    WHERE wm.workspace_id = %s
                    ORDER BY wm.joined_at ASC
                    """,
                    (workspace_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT wm.id, wm.workspace_id, wm.user_id, wm.role, wm.joined_at, NULL AS email, NULL AS name
                    FROM workspace_members wm
                    WHERE wm.workspace_id = ?
                    ORDER BY wm.joined_at ASC
                    """,
                    (workspace_id,),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                WorkspaceMemberRecord(
                    id=str(r[0]),
                    workspace_id=str(r[1]),
                    user_id=str(r[2]),
                    role=str(r[3]),
                    joined_at=r[4],
                    user_email=str(r[5]) if r[5] else None,
                    user_name=str(r[6]) if r[6] else None,
                )
                for r in rows
            ]
        finally:
            connection.close()

    def add_member(self, workspace_id: str, user_id: str, role: str = "analyst") -> WorkspaceMemberRecord:
        existing = self.get_member(workspace_id, user_id)
        if existing:
            return existing
        mem_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO workspace_members (id, workspace_id, user_id, role)
                VALUES (%s, %s, %s, %s)
                """,
                (mem_id, workspace_id, user_id, role),
            )
            connection.commit()
            cursor.close()
            return self.get_member(workspace_id, user_id)  # type: ignore
        finally:
            connection.close()

    def update_member_role(self, workspace_id: str, user_id: str, new_role: str) -> WorkspaceMemberRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE workspace_members
                SET role = %s
                WHERE workspace_id = %s AND user_id = %s
                """,
                (new_role, workspace_id, user_id),
            )
            connection.commit()
            cursor.close()
            mem = self.get_member(workspace_id, user_id)
            if not mem:
                raise WorkspaceNotFoundError(f"User `{user_id}` is not a member of workspace `{workspace_id}`.")
            return mem
        finally:
            connection.close()

    def remove_member(self, workspace_id: str, user_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def transfer_ownership(self, workspace_id: str, current_owner_id: str, new_owner_id: str) -> WorkspaceRecord:
        ws = self.get_workspace(workspace_id)
        if ws.owner_id != current_owner_id:
            raise WorkspaceAccessError("Only the current owner can transfer workspace ownership.")
        new_mem = self.get_member(workspace_id, new_owner_id)
        if not new_mem:
            raise WorkspaceAccessError("New owner must be a member of the workspace.")

        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            # 1. Set new owner on workspace table
            cursor.execute("UPDATE workspaces SET owner_id = %s WHERE id = %s", (new_owner_id, workspace_id))
            # 2. Update new owner role to 'owner'
            cursor.execute("UPDATE workspace_members SET role = 'owner' WHERE workspace_id = %s AND user_id = %s", (workspace_id, new_owner_id))
            # 3. Demote old owner to 'admin'
            cursor.execute("UPDATE workspace_members SET role = 'admin' WHERE workspace_id = %s AND user_id = %s", (workspace_id, current_owner_id))
            connection.commit()
            cursor.close()
            return self.get_workspace(workspace_id)
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # INVITATIONS
    # -------------------------------------------------------------------------

    def create_invitation(
        self,
        workspace_id: str,
        inviter_id: str,
        invitee_email: str,
        role: str,
        token_hash: str,
        expires_at: datetime,
    ) -> WorkspaceInvitationRecord:
        inv_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO workspace_invitations (id, workspace_id, inviter_id, invitee_email, role, token_hash, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (inv_id, workspace_id, inviter_id, invitee_email.lower(), role, token_hash, expires_at),
            )
            connection.commit()
            cursor.close()
            return self.get_invitation_by_id(inv_id)
        finally:
            connection.close()

    def get_invitation_by_id(self, invitation_id: str) -> WorkspaceInvitationRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT i.id, i.workspace_id, i.inviter_id, i.invitee_email, i.role, i.token_hash, i.expires_at, i.accepted_at, i.created_at, w.name, u.name
                    FROM workspace_invitations i
                    LEFT JOIN workspaces w ON i.workspace_id = w.id
                    LEFT JOIN users u ON i.inviter_id = u.id
                    WHERE i.id = %s
                    """,
                    (invitation_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT i.id, i.workspace_id, i.inviter_id, i.invitee_email, i.role, i.token_hash, i.expires_at, i.accepted_at, i.created_at, w.name, NULL AS inviter_name
                    FROM workspace_invitations i
                    LEFT JOIN workspaces w ON i.workspace_id = w.id
                    WHERE i.id = ?
                    """,
                    (invitation_id,),
                )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise WorkspaceNotFoundError(f"Invitation `{invitation_id}` not found.")
            return WorkspaceInvitationRecord(
                id=str(row[0]),
                workspace_id=str(row[1]),
                inviter_id=str(row[2]),
                invitee_email=str(row[3]),
                role=str(row[4]),
                token_hash=str(row[5]),
                expires_at=row[6],
                accepted_at=row[7],
                created_at=row[8],
                workspace_name=str(row[9]) if row[9] else None,
                inviter_name=str(row[10]) if row[10] else None,
            )
        finally:
            connection.close()

    def get_invitation_by_hash(self, token_hash: str) -> WorkspaceInvitationRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT i.id, i.workspace_id, i.inviter_id, i.invitee_email, i.role, i.token_hash, i.expires_at, i.accepted_at, i.created_at, w.name, u.name
                    FROM workspace_invitations i
                    LEFT JOIN workspaces w ON i.workspace_id = w.id
                    LEFT JOIN users u ON i.inviter_id = u.id
                    WHERE i.token_hash = %s
                    """,
                    (token_hash,),
                )
            else:
                cursor.execute(
                    """
                    SELECT i.id, i.workspace_id, i.inviter_id, i.invitee_email, i.role, i.token_hash, i.expires_at, i.accepted_at, i.created_at, w.name, NULL AS inviter_name
                    FROM workspace_invitations i
                    LEFT JOIN workspaces w ON i.workspace_id = w.id
                    WHERE i.token_hash = ?
                    """,
                    (token_hash,),
                )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return WorkspaceInvitationRecord(
                id=str(row[0]),
                workspace_id=str(row[1]),
                inviter_id=str(row[2]),
                invitee_email=str(row[3]),
                role=str(row[4]),
                token_hash=str(row[5]),
                expires_at=row[6],
                accepted_at=row[7],
                created_at=row[8],
                workspace_name=str(row[9]) if row[9] else None,
                inviter_name=str(row[10]) if row[10] else None,
            )
        finally:
            connection.close()

    def mark_invitation_accepted(self, invitation_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE workspace_invitations SET accepted_at = CURRENT_TIMESTAMP WHERE id = %s",
                (invitation_id,),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def list_workspace_invitations(self, workspace_id: str) -> list[WorkspaceInvitationRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT i.id, i.workspace_id, i.inviter_id, i.invitee_email, i.role, i.token_hash, i.expires_at, i.accepted_at, i.created_at, w.name, u.name
                    FROM workspace_invitations i
                    LEFT JOIN workspaces w ON i.workspace_id = w.id
                    LEFT JOIN users u ON i.inviter_id = u.id
                    WHERE i.workspace_id = %s
                    ORDER BY i.created_at DESC
                    """,
                    (workspace_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT i.id, i.workspace_id, i.inviter_id, i.invitee_email, i.role, i.token_hash, i.expires_at, i.accepted_at, i.created_at, w.name, NULL AS inviter_name
                    FROM workspace_invitations i
                    LEFT JOIN workspaces w ON i.workspace_id = w.id
                    WHERE i.workspace_id = ?
                    ORDER BY i.created_at DESC
                    """,
                    (workspace_id,),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                WorkspaceInvitationRecord(
                    id=str(r[0]),
                    workspace_id=str(r[1]),
                    inviter_id=str(r[2]),
                    invitee_email=str(r[3]),
                    role=str(r[4]),
                    token_hash=str(r[5]),
                    expires_at=r[6],
                    accepted_at=r[7],
                    created_at=r[8],
                    workspace_name=str(r[9]) if r[9] else None,
                    inviter_name=str(r[10]) if r[10] else None,
                )
                for r in rows
            ]
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # SHARED DATASETS
    # -------------------------------------------------------------------------

    def share_dataset(self, workspace_id: str, dataset_id: str, shared_by_user_id: str) -> WorkspaceDatasetRecord:
        wd_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._is_sqlite():
                cursor.execute(
                    """
                    INSERT INTO workspace_datasets (id, workspace_id, dataset_id, shared_by_user_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(workspace_id, dataset_id) DO UPDATE SET shared_by_user_id = excluded.shared_by_user_id
                    """,
                    (wd_id, workspace_id, dataset_id, shared_by_user_id),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO workspace_datasets (id, workspace_id, dataset_id, shared_by_user_id)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE shared_by_user_id = VALUES(shared_by_user_id)
                    """,
                    (wd_id, workspace_id, dataset_id, shared_by_user_id),
                )
            connection.commit()
            cursor.close()
            return self.get_shared_dataset(workspace_id, dataset_id)  # type: ignore
        finally:
            connection.close()

    def unshare_dataset(self, workspace_id: str, dataset_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM workspace_datasets WHERE workspace_id = %s AND dataset_id = %s",
                (workspace_id, dataset_id),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def get_shared_dataset(self, workspace_id: str, dataset_id: str) -> WorkspaceDatasetRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("datasets") and self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, d.dataset_name, u.name
                    FROM workspace_datasets wd
                    LEFT JOIN datasets d ON wd.dataset_id = d.dataset_id
                    LEFT JOIN users u ON wd.shared_by_user_id = u.id
                    WHERE wd.workspace_id = %s AND wd.dataset_id = %s
                    """,
                    (workspace_id, dataset_id),
                )
            elif self._table_exists("datasets"):
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, d.dataset_name, NULL AS user_name
                    FROM workspace_datasets wd
                    LEFT JOIN datasets d ON wd.dataset_id = d.dataset_id
                    WHERE wd.workspace_id = ? AND wd.dataset_id = ?
                    """,
                    (workspace_id, dataset_id),
                )
            elif self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, NULL AS dataset_name, u.name
                    FROM workspace_datasets wd
                    LEFT JOIN users u ON wd.shared_by_user_id = u.id
                    WHERE wd.workspace_id = ? AND wd.dataset_id = ?
                    """,
                    (workspace_id, dataset_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, NULL AS dataset_name, NULL AS user_name
                    FROM workspace_datasets wd
                    WHERE wd.workspace_id = ? AND wd.dataset_id = ?
                    """,
                    (workspace_id, dataset_id),
                )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            return WorkspaceDatasetRecord(
                id=str(row[0]),
                workspace_id=str(row[1]),
                dataset_id=str(row[2]),
                shared_by_user_id=str(row[3]),
                created_at=row[4],
                dataset_name=str(row[5]) if row[5] else None,
                shared_by_user_name=str(row[6]) if row[6] else None,
            )
        finally:
            connection.close()

    def list_shared_datasets(self, workspace_id: str) -> list[WorkspaceDatasetRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("datasets") and self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, d.dataset_name, u.name
                    FROM workspace_datasets wd
                    LEFT JOIN datasets d ON wd.dataset_id = d.dataset_id
                    LEFT JOIN users u ON wd.shared_by_user_id = u.id
                    WHERE wd.workspace_id = %s
                    ORDER BY wd.created_at DESC
                    """,
                    (workspace_id,),
                )
            elif self._table_exists("datasets"):
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, d.dataset_name, NULL AS user_name
                    FROM workspace_datasets wd
                    LEFT JOIN datasets d ON wd.dataset_id = d.dataset_id
                    WHERE wd.workspace_id = ?
                    ORDER BY wd.created_at DESC
                    """,
                    (workspace_id,),
                )
            elif self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, NULL AS dataset_name, u.name
                    FROM workspace_datasets wd
                    LEFT JOIN users u ON wd.shared_by_user_id = u.id
                    WHERE wd.workspace_id = ?
                    ORDER BY wd.created_at DESC
                    """,
                    (workspace_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT wd.id, wd.workspace_id, wd.dataset_id, wd.shared_by_user_id, wd.created_at, NULL AS dataset_name, NULL AS user_name
                    FROM workspace_datasets wd
                    WHERE wd.workspace_id = ?
                    ORDER BY wd.created_at DESC
                    """,
                    (workspace_id,),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                WorkspaceDatasetRecord(
                    id=str(r[0]),
                    workspace_id=str(r[1]),
                    dataset_id=str(r[2]),
                    shared_by_user_id=str(r[3]),
                    created_at=r[4],
                    dataset_name=str(r[5]) if r[5] else None,
                    shared_by_user_name=str(r[6]) if r[6] else None,
                )
                for r in rows
            ]
        finally:
            connection.close()

    def is_dataset_shared_with_user_workspace(self, dataset_id: str, user_id: str) -> bool:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM workspace_datasets wd
                JOIN workspace_members wm ON wd.workspace_id = wm.workspace_id
                WHERE wd.dataset_id = %s AND wm.user_id = %s
                LIMIT 1
                """,
                (dataset_id, user_id),
            )
            row = cursor.fetchone()
            cursor.close()
            return bool(row)
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # SHARED ANALYSIS RESULTS & COMMENTS
    # -------------------------------------------------------------------------

    def share_analysis_result(
        self,
        workspace_id: str,
        dataset_id: str,
        user_id: str,
        question: str,
        answer: str,
        metrics: dict[str, Any] | None = None,
        chart: dict[str, Any] | None = None,
        insights: list[str] | None = None,
    ) -> WorkspaceAnalysisResultRecord:
        res_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO workspace_analysis_results (id, workspace_id, dataset_id, user_id, question, answer, metrics_json, chart_json, insights_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    res_id,
                    workspace_id,
                    dataset_id,
                    user_id,
                    question,
                    answer,
                    json.dumps(metrics) if metrics else None,
                    json.dumps(chart) if chart else None,
                    json.dumps(insights) if insights else None,
                ),
            )
            connection.commit()
            cursor.close()
            return self.get_analysis_result(res_id)
        finally:
            connection.close()

    def get_analysis_result(self, result_id: str) -> WorkspaceAnalysisResultRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT r.id, r.workspace_id, r.dataset_id, r.user_id, r.question, r.answer, r.metrics_json, r.chart_json, r.insights_json, r.created_at, u.name
                    FROM workspace_analysis_results r
                    LEFT JOIN users u ON r.user_id = u.id
                    WHERE r.id = %s
                    """,
                    (result_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT r.id, r.workspace_id, r.dataset_id, r.user_id, r.question, r.answer, r.metrics_json, r.chart_json, r.insights_json, r.created_at, NULL AS user_name
                    FROM workspace_analysis_results r
                    WHERE r.id = ?
                    """,
                    (result_id,),
                )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise WorkspaceNotFoundError(f"Analysis result `{result_id}` not found.")
            return WorkspaceAnalysisResultRecord(
                id=str(row[0]),
                workspace_id=str(row[1]),
                dataset_id=str(row[2]),
                user_id=str(row[3]),
                question=str(row[4]),
                answer=str(row[5]),
                metrics_json=str(row[6]) if row[6] else None,
                chart_json=str(row[7]) if row[7] else None,
                insights_json=str(row[8]) if row[8] else None,
                created_at=row[9],
                user_name=str(row[10]) if row[10] else None,
            )
        finally:
            connection.close()

    def list_analysis_results(self, workspace_id: str, limit: int = 50) -> list[WorkspaceAnalysisResultRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT r.id, r.workspace_id, r.dataset_id, r.user_id, r.question, r.answer, r.metrics_json, r.chart_json, r.insights_json, r.created_at, u.name
                    FROM workspace_analysis_results r
                    LEFT JOIN users u ON r.user_id = u.id
                    WHERE r.workspace_id = %s
                    ORDER BY r.created_at DESC
                    LIMIT %s
                    """,
                    (workspace_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT r.id, r.workspace_id, r.dataset_id, r.user_id, r.question, r.answer, r.metrics_json, r.chart_json, r.insights_json, r.created_at, NULL AS user_name
                    FROM workspace_analysis_results r
                    WHERE r.workspace_id = ?
                    ORDER BY r.created_at DESC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                WorkspaceAnalysisResultRecord(
                    id=str(r[0]),
                    workspace_id=str(r[1]),
                    dataset_id=str(r[2]),
                    user_id=str(r[3]),
                    question=str(r[4]),
                    answer=str(r[5]),
                    metrics_json=str(r[6]) if r[6] else None,
                    chart_json=str(r[7]) if r[7] else None,
                    insights_json=str(r[8]) if r[8] else None,
                    created_at=r[9],
                    user_name=str(r[10]) if r[10] else None,
                )
                for r in rows
            ]
        finally:
            connection.close()

    def add_comment(self, result_id: str, user_id: str, comment_text: str) -> AnalysisCommentRecord:
        cid = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO analysis_comments (id, result_id, user_id, comment_text)
                VALUES (%s, %s, %s, %s)
                """,
                (cid, result_id, user_id, comment_text),
            )
            connection.commit()
            cursor.close()
            return self.get_comment(cid)
        finally:
            connection.close()

    def get_comment(self, comment_id: str) -> AnalysisCommentRecord:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT c.id, c.result_id, c.user_id, c.comment_text, c.created_at, u.name
                    FROM analysis_comments c
                    LEFT JOIN users u ON c.user_id = u.id
                    WHERE c.id = %s
                    """,
                    (comment_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT c.id, c.result_id, c.user_id, c.comment_text, c.created_at, NULL AS user_name
                    FROM analysis_comments c
                    WHERE c.id = ?
                    """,
                    (comment_id,),
                )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise WorkspaceNotFoundError(f"Comment `{comment_id}` not found.")
            return AnalysisCommentRecord(
                id=str(row[0]),
                result_id=str(row[1]),
                user_id=str(row[2]),
                comment_text=str(row[3]),
                created_at=row[4],
                user_name=str(row[5]) if row[5] else None,
            )
        finally:
            connection.close()

    def list_comments(self, result_id: str) -> list[AnalysisCommentRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT c.id, c.result_id, c.user_id, c.comment_text, c.created_at, u.name
                    FROM analysis_comments c
                    LEFT JOIN users u ON c.user_id = u.id
                    WHERE c.result_id = %s
                    ORDER BY c.created_at ASC
                    """,
                    (result_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT c.id, c.result_id, c.user_id, c.comment_text, c.created_at, NULL AS user_name
                    FROM analysis_comments c
                    WHERE c.result_id = ?
                    ORDER BY c.created_at ASC
                    """,
                    (result_id,),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                AnalysisCommentRecord(
                    id=str(r[0]),
                    result_id=str(r[1]),
                    user_id=str(r[2]),
                    comment_text=str(r[3]),
                    created_at=r[4],
                    user_name=str(r[5]) if r[5] else None,
                )
                for r in rows
            ]
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # ACTIVITY LOGS & NOTIFICATIONS
    # -------------------------------------------------------------------------

    def log_activity(
        self,
        workspace_id: str,
        user_id: str | None,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        log_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO workspace_activity_logs (id, workspace_id, user_id, event_type, metadata_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (log_id, workspace_id, user_id, event_type, json.dumps(metadata) if metadata else None),
            )
            connection.commit()
            cursor.close()
            return log_id
        except Exception as err:
            _log.warning("Failed to log workspace activity %s: %s", event_type, err)
            return log_id
        finally:
            connection.close()

    def list_activity_logs(self, workspace_id: str, limit: int = 50) -> list[WorkspaceActivityLogRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self._table_exists("users"):
                cursor.execute(
                    """
                    SELECT l.id, l.workspace_id, l.user_id, l.event_type, l.metadata_json, l.created_at, u.name
                    FROM workspace_activity_logs l
                    LEFT JOIN users u ON l.user_id = u.id
                    WHERE l.workspace_id = %s
                    ORDER BY l.created_at DESC
                    LIMIT %s
                    """,
                    (workspace_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT l.id, l.workspace_id, l.user_id, l.event_type, l.metadata_json, l.created_at, NULL AS user_name
                    FROM workspace_activity_logs l
                    WHERE l.workspace_id = ?
                    ORDER BY l.created_at DESC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                )
            rows = cursor.fetchall()
            cursor.close()
            return [
                WorkspaceActivityLogRecord(
                    id=str(r[0]),
                    workspace_id=str(r[1]),
                    user_id=str(r[2]) if r[2] else None,
                    event_type=str(r[3]),
                    metadata_json=str(r[4]) if r[4] else None,
                    created_at=r[5],
                    user_name=str(r[6]) if r[6] else None,
                )
                for r in rows
            ]
        finally:
            connection.close()

    def create_notification(self, user_id: str, title: str, message: str, notification_id: str | None = None) -> NotificationRecord:
        nid = notification_id or str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            statement = (
                "INSERT OR IGNORE INTO user_notifications (id, user_id, title, message, is_read) VALUES (%s, %s, %s, %s, 0)"
                if self._is_sqlite()
                else "INSERT IGNORE INTO user_notifications (id, user_id, title, message, is_read) VALUES (%s, %s, %s, %s, 0)"
            ) if notification_id else "INSERT INTO user_notifications (id, user_id, title, message, is_read) VALUES (%s, %s, %s, %s, 0)"
            cursor.execute(statement, (nid, user_id, title, message))
            connection.commit()
            cursor.close()
            return NotificationRecord(
                id=nid,
                user_id=user_id,
                title=title,
                message=message,
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
        finally:
            connection.close()

    def list_user_notifications(self, user_id: str, limit: int = 20) -> list[NotificationRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, user_id, title, message, is_read, created_at
                FROM user_notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                NotificationRecord(
                    id=str(r[0]),
                    user_id=str(r[1]),
                    title=str(r[2]),
                    message=str(r[3]),
                    is_read=bool(r[4]),
                    created_at=r[5],
                )
                for r in rows
            ]
        finally:
            connection.close()

    def mark_notification_read(self, notification_id: str, user_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE user_notifications SET is_read = 1 WHERE id = %s AND user_id = %s",
                (notification_id, user_id),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

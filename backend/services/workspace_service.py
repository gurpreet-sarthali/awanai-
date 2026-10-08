"""Workspace Service enforcing role-based permissions and collaboration workflows for Phase 18."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.core.config import settings
from backend.core.user_model import UserRecord
from backend.repositories.workspace_repository import (
    AnalysisCommentRecord,
    WorkspaceAccessError,
    WorkspaceActivityLogRecord,
    WorkspaceAnalysisResultRecord,
    WorkspaceConflictError,
    WorkspaceDatasetRecord,
    WorkspaceInvitationRecord,
    WorkspaceMemberRecord,
    WorkspaceNotFoundError,
    WorkspaceRecord,
    WorkspaceRepository,
)


class RolePermissions:
    OWNER = "owner"
    ADMIN = "admin"
    AUDITOR = "auditor"
    ANALYST = "analyst"
    VIEWER = "viewer"
    GUEST = "guest"

    ALL_ROLES = {OWNER, ADMIN, AUDITOR, ANALYST, VIEWER, GUEST}

    ROLE_HIERARCHY = {
        OWNER: 60,
        ADMIN: 50,
        AUDITOR: 40,
        ANALYST: 30,
        VIEWER: 20,
        GUEST: 10,
    }

    ALL_PERMISSIONS = {
        "manage_members",
        "manage_datasets",
        "share_analysis",
        "view_data",
        "manage_workspace",
        "view_audit_logs",
        "manage_security",
    }

    @classmethod
    def permission_set(cls, role: str) -> set[str]:
        mapping = {
            cls.OWNER: cls.ALL_PERMISSIONS,
            cls.ADMIN: {"manage_members", "manage_datasets", "share_analysis", "view_data", "manage_workspace", "view_audit_logs", "manage_security"},
            cls.AUDITOR: {"view_data", "view_audit_logs"},
            cls.ANALYST: {"manage_datasets", "share_analysis", "view_data"},
            cls.VIEWER: {"view_data"},
            cls.GUEST: set(),
        }
        return mapping.get(role, set())

    @classmethod
    def role_metadata(cls) -> dict[str, dict[str, Any]]:
        return {
            role: {
                "level": cls.ROLE_HIERARCHY.get(role, 0),
                "permissions": sorted(cls.permission_set(role)),
            }
            for role in sorted(cls.ALL_ROLES, key=lambda r: cls.ROLE_HIERARCHY.get(r, 0), reverse=True)
        }

    @classmethod
    def can_manage_members(cls, role: str) -> bool:
        return "manage_members" in cls.permission_set(role)

    @classmethod
    def can_manage_datasets(cls, role: str) -> bool:
        return "manage_datasets" in cls.permission_set(role)

    @classmethod
    def can_analyze(cls, role: str) -> bool:
        return "share_analysis" in cls.permission_set(role)

    @classmethod
    def can_view(cls, role: str) -> bool:
        return "view_data" in cls.permission_set(role)

    @classmethod
    def can_manage_workspace(cls, role: str) -> bool:
        return "manage_workspace" in cls.permission_set(role)

    @classmethod
    def can_view_audit_logs(cls, role: str) -> bool:
        return "view_audit_logs" in cls.permission_set(role)

    @classmethod
    def can_manage_security(cls, role: str) -> bool:
        return "manage_security" in cls.permission_set(role)

    @classmethod
    def can_transfer_or_delete_workspace(cls, role: str) -> bool:
        return role == cls.OWNER


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository) -> None:
        self.repository = repository

    @staticmethod
    def _normalize_datetime(value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    # -------------------------------------------------------------------------
    # WORKSPACE MANAGEMENT
    # -------------------------------------------------------------------------

    def create_workspace(self, user: UserRecord, name: str, description: str | None = None) -> WorkspaceRecord:
        if not name or not name.strip():
            raise ValueError("Workspace name cannot be empty.")
        ws = self.repository.create_workspace(name.strip(), user.id, description.strip() if description else None)
        self.repository.log_activity(
            workspace_id=ws.id,
            user_id=user.id,
            event_type="workspace_created",
            metadata={"name": ws.name},
        )
        return ws

    def get_workspace(self, workspace_id: str, user: UserRecord) -> WorkspaceRecord:
        mem = self.repository.get_member(workspace_id, user.id)
        if not mem and not user.is_admin:
            raise WorkspaceAccessError("You are not a member of this workspace.")
        return self.repository.get_workspace(workspace_id)

    def list_user_workspaces(self, user: UserRecord) -> list[WorkspaceRecord]:
        return self.repository.list_workspaces_for_user(user.id)

    def update_workspace(self, workspace_id: str, user: UserRecord, name: str | None = None, description: str | None = None) -> WorkspaceRecord:
        role = self._require_role(workspace_id, user, min_role=RolePermissions.ADMIN)
        updated = self.repository.update_workspace(workspace_id, name, description)
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=user.id,
            event_type="workspace_updated",
            metadata={"name": updated.name},
        )
        return updated

    def delete_workspace(self, workspace_id: str, user: UserRecord) -> None:
        self._require_role(workspace_id, user, min_role=RolePermissions.OWNER)
        self.repository.delete_workspace(workspace_id)

    # -------------------------------------------------------------------------
    # MEMBERSHIP & ROLES
    # -------------------------------------------------------------------------

    def list_members(self, workspace_id: str, user: UserRecord) -> list[WorkspaceMemberRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        return self.repository.list_members(workspace_id)

    def update_member_role(self, workspace_id: str, actor: UserRecord, target_user_id: str, new_role: str) -> WorkspaceMemberRecord:
        if new_role not in RolePermissions.ALL_ROLES:
            raise ValueError(f"Invalid role `{new_role}`.")
        if new_role == RolePermissions.OWNER:
            raise WorkspaceAccessError("Use transfer ownership to assign the Owner role.")

        actor_mem = self._require_member(workspace_id, actor)
        if not RolePermissions.can_manage_members(actor_mem.role):
            raise WorkspaceAccessError("Only Workspace Owners and Admins can manage member roles.")

        target_mem = self.repository.get_member(workspace_id, target_user_id)
        if not target_mem:
            raise WorkspaceNotFoundError(f"User `{target_user_id}` is not a member of this workspace.")

        if target_mem.role == RolePermissions.OWNER:
            raise WorkspaceAccessError("Cannot change role of the workspace Owner directly.")

        if actor_mem.role == RolePermissions.ADMIN and target_mem.role == RolePermissions.ADMIN:
            raise WorkspaceAccessError("Admins cannot change roles of other Admins.")

        updated = self.repository.update_member_role(workspace_id, target_user_id, new_role)
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=actor.id,
            event_type="role_changed",
            metadata={"target_user_id": target_user_id, "new_role": new_role},
        )
        self.repository.create_notification(
            user_id=target_user_id,
            title="Workspace Role Changed",
            message=f"Your role in workspace `{workspace_id}` was updated to `{new_role}`.",
        )
        return updated

    def remove_member(self, workspace_id: str, actor: UserRecord, target_user_id: str) -> None:
        actor_mem = self._require_member(workspace_id, actor)
        target_mem = self.repository.get_member(workspace_id, target_user_id)
        if not target_mem:
            raise WorkspaceNotFoundError(f"User `{target_user_id}` is not a member of this workspace.")

        if target_mem.role == RolePermissions.OWNER:
            raise WorkspaceAccessError("The workspace Owner cannot be removed. Transfer ownership first.")

        if actor.id != target_user_id:
            # Removing someone else
            if not RolePermissions.can_manage_members(actor_mem.role):
                raise WorkspaceAccessError("Only Owners and Admins can remove members.")
            if actor_mem.role == RolePermissions.ADMIN and target_mem.role in {RolePermissions.OWNER, RolePermissions.ADMIN}:
                raise WorkspaceAccessError("Admins cannot remove Owners or other Admins.")

        self.repository.remove_member(workspace_id, target_user_id)
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=actor.id,
            event_type="member_removed" if actor.id != target_user_id else "member_left",
            metadata={"target_user_id": target_user_id},
        )

    def transfer_ownership(self, workspace_id: str, current_owner: UserRecord, new_owner_user_id: str) -> WorkspaceRecord:
        self._require_role(workspace_id, current_owner, min_role=RolePermissions.OWNER)
        updated = self.repository.transfer_ownership(workspace_id, current_owner.id, new_owner_user_id)
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=current_owner.id,
            event_type="ownership_transferred",
            metadata={"new_owner_id": new_owner_user_id},
        )
        self.repository.create_notification(
            user_id=new_owner_user_id,
            title="Workspace Ownership Transferred",
            message=f"You are now the Owner of workspace `{updated.name}`.",
        )
        return updated

    # -------------------------------------------------------------------------
    # INVITATIONS
    # -------------------------------------------------------------------------

    def create_invitation(self, workspace_id: str, inviter: UserRecord, invitee_email: str, role: str = "analyst") -> tuple[WorkspaceInvitationRecord, str]:
        if role not in RolePermissions.ALL_ROLES or role == RolePermissions.OWNER:
            raise ValueError(f"Invalid invitation role `{role}`.")

        actor_mem = self._require_member(workspace_id, inviter)
        if not RolePermissions.can_manage_members(actor_mem.role):
            raise WorkspaceAccessError("Only Workspace Owners and Admins can invite new members.")

        # Generate token and token_hash
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        inv = self.repository.create_invitation(
            workspace_id=workspace_id,
            inviter_id=inviter.id,
            invitee_email=invitee_email.lower().strip(),
            role=role,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=inviter.id,
            event_type="member_invited",
            metadata={"invitee_email": invitee_email, "role": role},
        )
        return inv, raw_token

    def accept_invitation(self, raw_token: str, accepting_user: UserRecord) -> WorkspaceMemberRecord:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        inv = self.repository.get_invitation_by_hash(token_hash)
        if not inv:
            raise WorkspaceNotFoundError("Invalid or expired invitation token.")

        if inv.accepted_at is not None:
            raise WorkspaceConflictError("This invitation has already been accepted.")

        now = datetime.now(timezone.utc)
        expires_at = self._normalize_datetime(inv.expires_at)
        if expires_at is None:
            raise WorkspaceAccessError("This invitation link is invalid.")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            raise WorkspaceAccessError("This invitation link has expired.")

        # Add member to workspace
        mem = self.repository.add_member(inv.workspace_id, accepting_user.id, role=inv.role)
        self.repository.mark_invitation_accepted(inv.id)
        self.repository.log_activity(
            workspace_id=inv.workspace_id,
            user_id=accepting_user.id,
            event_type="member_joined",
            metadata={"role": inv.role},
        )
        return mem

    def list_invitations(self, workspace_id: str, user: UserRecord) -> list[WorkspaceInvitationRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.ADMIN)
        return self.repository.list_workspace_invitations(workspace_id)

    # -------------------------------------------------------------------------
    # DATASET SHARING
    # -------------------------------------------------------------------------

    def share_dataset(self, workspace_id: str, user: UserRecord, dataset_id: str) -> WorkspaceDatasetRecord:
        role = self._require_role(workspace_id, user, min_role=RolePermissions.ANALYST)
        if not RolePermissions.can_manage_datasets(role):
            raise WorkspaceAccessError("Your workspace role does not permit dataset sharing.")

        wd = self.repository.share_dataset(workspace_id, dataset_id, user.id)
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=user.id,
            event_type="dataset_shared",
            metadata={"dataset_id": dataset_id},
        )
        return wd

    def unshare_dataset(self, workspace_id: str, user: UserRecord, dataset_id: str) -> None:
        role = self._require_role(workspace_id, user, min_role=RolePermissions.ANALYST)
        if not RolePermissions.can_manage_datasets(role):
            raise WorkspaceAccessError("Your workspace role does not permit unsharing datasets.")

        self.repository.unshare_dataset(workspace_id, dataset_id)
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=user.id,
            event_type="dataset_unshared",
            metadata={"dataset_id": dataset_id},
        )

    def list_shared_datasets(self, workspace_id: str, user: UserRecord) -> list[WorkspaceDatasetRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        return self.repository.list_shared_datasets(workspace_id)

    # -------------------------------------------------------------------------
    # SHARED ANALYSIS RESULTS & COMMENTS
    # -------------------------------------------------------------------------

    def share_analysis_result(
        self,
        workspace_id: str,
        user: UserRecord,
        dataset_id: str,
        question: str,
        answer: str,
        metrics: dict[str, Any] | None = None,
        chart: dict[str, Any] | None = None,
        insights: list[str] | None = None,
    ) -> WorkspaceAnalysisResultRecord:
        role = self._require_role(workspace_id, user, min_role=RolePermissions.ANALYST)
        if not RolePermissions.can_analyze(role):
            raise WorkspaceAccessError("Your workspace role does not permit sharing analysis results.")

        result = self.repository.share_analysis_result(
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            user_id=user.id,
            question=question,
            answer=answer,
            metrics=metrics,
            chart=chart,
            insights=insights,
        )
        self.repository.log_activity(
            workspace_id=workspace_id,
            user_id=user.id,
            event_type="analysis_shared",
            metadata={"result_id": result.id, "question": question},
        )
        return result

    def list_shared_analysis_results(self, workspace_id: str, user: UserRecord, limit: int = 50) -> list[WorkspaceAnalysisResultRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        return self.repository.list_analysis_results(workspace_id, limit)

    def add_comment(self, workspace_id: str, user: UserRecord, result_id: str, comment_text: str) -> AnalysisCommentRecord:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        if not comment_text or not comment_text.strip():
            raise ValueError("Comment text cannot be empty.")

        return self.repository.add_comment(result_id, user.id, comment_text.strip())

    def list_comments(self, workspace_id: str, user: UserRecord, result_id: str) -> list[AnalysisCommentRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        return self.repository.list_comments(result_id)

    # -------------------------------------------------------------------------
    # ACTIVITY LOGS & NOTIFICATIONS
    # -------------------------------------------------------------------------

    def list_activity_logs(self, workspace_id: str, user: UserRecord, limit: int = 50) -> list[WorkspaceActivityLogRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        return self.repository.list_activity_logs(workspace_id, limit)

    def list_workspace_audit_logs(self, workspace_id: str, user: UserRecord, limit: int = 50) -> list[WorkspaceActivityLogRecord]:
        self._require_role(workspace_id, user, min_role=RolePermissions.ADMIN)
        return self.repository.list_activity_logs(workspace_id, limit)

    def log_workspace_event(
        self,
        workspace_id: str,
        user: UserRecord,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        return self.repository.log_activity(workspace_id=workspace_id, user_id=user.id, event_type=event_type, metadata=metadata)

    def get_role_capabilities(self) -> dict[str, Any]:
        return {
            "roles": RolePermissions.role_metadata(),
            "default_role": RolePermissions.ANALYST,
            "enterprise_roles": [RolePermissions.OWNER, RolePermissions.ADMIN, RolePermissions.AUDITOR, RolePermissions.ANALYST, RolePermissions.VIEWER, RolePermissions.GUEST],
        }

    # -------------------------------------------------------------------------
    # HELPER PERMISSION CHECKS
    # -------------------------------------------------------------------------

    def _require_member(self, workspace_id: str, user: UserRecord) -> WorkspaceMemberRecord:
        mem = self.repository.get_member(workspace_id, user.id)
        if not mem:
            if user.is_admin or user.email.lower() in settings.admin_emails:
                return WorkspaceMemberRecord(
                    id=f"admin-{user.id}",
                    workspace_id=workspace_id,
                    user_id=user.id,
                    role=RolePermissions.OWNER,
                    joined_at=datetime.now(timezone.utc),
                    user_email=user.email,
                    user_name=user.name,
                )
            raise WorkspaceAccessError("You are not a member of this workspace.")
        return mem

    def _require_role(self, workspace_id: str, user: UserRecord, min_role: str) -> str:
        mem = self._require_member(workspace_id, user)
        req_level = RolePermissions.ROLE_HIERARCHY.get(min_role, 0)
        user_level = RolePermissions.ROLE_HIERARCHY.get(mem.role, 0)
        if user_level < req_level:
            raise WorkspaceAccessError(f"Operation requires minimum workspace role `{min_role}`.")
        return mem.role

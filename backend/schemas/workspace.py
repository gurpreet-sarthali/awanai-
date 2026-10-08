"""Pydantic schemas for Phase 18 Workspaces, Invitations, Collaboration, and Activity."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import Field
from .common import APIModel

WorkspaceRole = Literal["owner", "admin", "auditor", "analyst", "viewer", "guest"]


class CreateWorkspaceRequest(APIModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class UpdateWorkspaceRequest(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class WorkspaceResponse(APIModel):
    id: str
    name: str
    description: str | None = None
    owner_id: str
    created_at: str
    updated_at: str


class WorkspaceMemberResponse(APIModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    joined_at: str
    user_email: str | None = None
    user_name: str | None = None


class UpdateMemberRoleRequest(APIModel):
    role: WorkspaceRole


class TransferOwnershipRequest(APIModel):
    new_owner_user_id: str


class InviteMemberRequest(APIModel):
    email: str
    role: WorkspaceRole = "analyst"


class InvitationResponse(APIModel):
    id: str
    workspace_id: str
    inviter_id: str
    invitee_email: str
    role: str
    expires_at: str
    accepted_at: str | None = None
    created_at: str
    workspace_name: str | None = None
    inviter_name: str | None = None
    invite_url: str | None = None


class AcceptInvitationRequest(APIModel):
    token: str


class ShareDatasetRequest(APIModel):
    dataset_id: str


class SharedDatasetResponse(APIModel):
    id: str
    workspace_id: str
    dataset_id: str
    shared_by_user_id: str
    created_at: str
    dataset_name: str | None = None
    shared_by_user_name: str | None = None


class ShareAnalysisResultRequest(APIModel):
    dataset_id: str
    question: str
    answer: str
    metrics: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None
    insights: list[str] | None = None


class SharedAnalysisResultResponse(APIModel):
    id: str
    workspace_id: str
    dataset_id: str
    user_id: str
    question: str
    answer: str
    metrics: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None
    insights: list[str] | None = None
    created_at: str
    user_name: str | None = None


class CreateCommentRequest(APIModel):
    comment_text: str = Field(min_length=1, max_length=2000)


class AnalysisCommentResponse(APIModel):
    id: str
    result_id: str
    user_id: str
    comment_text: str
    created_at: str
    user_name: str | None = None


class ActivityLogResponse(APIModel):
    id: str
    workspace_id: str
    user_id: str | None = None
    event_type: str
    metadata: dict[str, Any] | None = None
    created_at: str
    user_name: str | None = None


class UserNotificationResponse(APIModel):
    id: str
    user_id: str
    title: str
    message: str
    is_read: bool
    created_at: str

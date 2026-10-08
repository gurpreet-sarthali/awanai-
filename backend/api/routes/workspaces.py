"""Workspaces, Collaboration & Sharing API routes for Phase 18."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, status

from backend.api.dependencies import get_chat_repository, get_current_user, get_workspace_service
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.repositories.chat_repository import ChatRepository
from backend.repositories.workspace_repository import (
    WorkspaceAccessError,
    WorkspaceConflictError,
    WorkspaceNotFoundError,
)
from backend.schemas.chat import ConversationSummary
from backend.schemas.workspace import (
    AcceptInvitationRequest,
    ActivityLogResponse,
    AnalysisCommentResponse,
    CreateCommentRequest,
    CreateWorkspaceRequest,
    InviteMemberRequest,
    InvitationResponse,
    ShareAnalysisResultRequest,
    ShareDatasetRequest,
    SharedAnalysisResultResponse,
    SharedDatasetResponse,
    TransferOwnershipRequest,
    UpdateMemberRoleRequest,
    UpdateWorkspaceRequest,
    UserNotificationResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from backend.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
invitations_router = APIRouter(prefix="/invitations", tags=["invitations"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


def _handle_error(err: Exception) -> AppError:
    if isinstance(err, WorkspaceNotFoundError):
        return AppError(404, "workspace_not_found", str(err))
    if isinstance(err, WorkspaceAccessError):
        return AppError(403, "workspace_forbidden", str(err))
    if isinstance(err, WorkspaceConflictError):
        return AppError(409, "workspace_conflict", str(err))
    if isinstance(err, ValueError):
        return AppError(400, "invalid_workspace_request", str(err))
    return AppError(500, "workspace_error", "A workspace error occurred.")


# -----------------------------------------------------------------------------
# WORKSPACES CRUD
# -----------------------------------------------------------------------------

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: CreateWorkspaceRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    try:
        ws = service.create_workspace(user, name=payload.name, description=payload.description)
        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            created_at=ws.created_at.isoformat(),
            updated_at=ws.updated_at.isoformat(),
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceResponse]:
    workspaces = service.list_user_workspaces(user)
    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            created_at=ws.created_at.isoformat(),
            updated_at=ws.updated_at.isoformat(),
        )
        for ws in workspaces
    ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    try:
        ws = service.get_workspace(workspace_id, user)
        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            created_at=ws.created_at.isoformat(),
            updated_at=ws.updated_at.isoformat(),
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: str,
    payload: UpdateWorkspaceRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    try:
        ws = service.update_workspace(workspace_id, user, name=payload.name, description=payload.description)
        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            created_at=ws.created_at.isoformat(),
            updated_at=ws.updated_at.isoformat(),
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    try:
        service.delete_workspace(workspace_id, user)
    except Exception as err:
        raise _handle_error(err) from err


# -----------------------------------------------------------------------------
# MEMBERS & ROLES
# -----------------------------------------------------------------------------

@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
def list_members(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceMemberResponse]:
    try:
        members = service.list_members(workspace_id, user)
        return [
            WorkspaceMemberResponse(
                id=m.id,
                workspace_id=m.workspace_id,
                user_id=m.user_id,
                role=m.role,
                joined_at=m.joined_at.isoformat(),
                user_email=m.user_email,
                user_name=m.user_name,
            )
            for m in members
        ]
    except Exception as err:
        raise _handle_error(err) from err


@router.patch("/{workspace_id}/members/{target_user_id}", response_model=WorkspaceMemberResponse)
def update_member_role(
    workspace_id: str,
    target_user_id: str,
    payload: UpdateMemberRoleRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceMemberResponse:
    try:
        m = service.update_member_role(workspace_id, actor=user, target_user_id=target_user_id, new_role=payload.role)
        return WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at.isoformat(),
            user_email=m.user_email,
            user_name=m.user_name,
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.delete("/{workspace_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: str,
    target_user_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    try:
        service.remove_member(workspace_id, actor=user, target_user_id=target_user_id)
    except Exception as err:
        raise _handle_error(err) from err


@router.post("/{workspace_id}/transfer-ownership", response_model=WorkspaceResponse)
def transfer_ownership(
    workspace_id: str,
    payload: TransferOwnershipRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceResponse:
    try:
        ws = service.transfer_ownership(workspace_id, current_owner=user, new_owner_user_id=payload.new_owner_user_id)
        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            owner_id=ws.owner_id,
            created_at=ws.created_at.isoformat(),
            updated_at=ws.updated_at.isoformat(),
        )
    except Exception as err:
        raise _handle_error(err) from err


# -----------------------------------------------------------------------------
# INVITATIONS
# -----------------------------------------------------------------------------

@router.post("/{workspace_id}/members/invite", response_model=InvitationResponse)
def invite_member(
    workspace_id: str,
    payload: InviteMemberRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> InvitationResponse:
    try:
        inv, raw_token = service.create_invitation(
            workspace_id=workspace_id,
            inviter=user,
            invitee_email=payload.email,
            role=payload.role,
        )
        return InvitationResponse(
            id=inv.id,
            workspace_id=inv.workspace_id,
            inviter_id=inv.inviter_id,
            invitee_email=inv.invitee_email,
            role=inv.role,
            expires_at=inv.expires_at.isoformat(),
            accepted_at=inv.accepted_at.isoformat() if inv.accepted_at else None,
            created_at=inv.created_at.isoformat(),
            workspace_name=inv.workspace_name,
            inviter_name=inv.inviter_name,
            invite_url=f"/invitations/accept?token={raw_token}",
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.get("/{workspace_id}/invitations", response_model=list[InvitationResponse])
def list_workspace_invitations(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[InvitationResponse]:
    try:
        invitations = service.list_invitations(workspace_id, user)
        return [
            InvitationResponse(
                id=inv.id,
                workspace_id=inv.workspace_id,
                inviter_id=inv.inviter_id,
                invitee_email=inv.invitee_email,
                role=inv.role,
                expires_at=inv.expires_at.isoformat(),
                accepted_at=inv.accepted_at.isoformat() if inv.accepted_at else None,
                created_at=inv.created_at.isoformat(),
                workspace_name=inv.workspace_name,
                inviter_name=inv.inviter_name,
            )
            for inv in invitations
        ]
    except Exception as err:
        raise _handle_error(err) from err


@invitations_router.post("/accept", response_model=WorkspaceMemberResponse)
def accept_invitation(
    payload: AcceptInvitationRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceMemberResponse:
    try:
        m = service.accept_invitation(payload.token, accepting_user=user)
        return WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at.isoformat(),
            user_email=m.user_email,
            user_name=m.user_name,
        )
    except Exception as err:
        raise _handle_error(err) from err


# -----------------------------------------------------------------------------
# DATASET SHARING
# -----------------------------------------------------------------------------

@router.post("/{workspace_id}/datasets/share", response_model=SharedDatasetResponse)
def share_dataset(
    workspace_id: str,
    payload: ShareDatasetRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SharedDatasetResponse:
    try:
        wd = service.share_dataset(workspace_id, user, dataset_id=payload.dataset_id)
        return SharedDatasetResponse(
            id=wd.id,
            workspace_id=wd.workspace_id,
            dataset_id=wd.dataset_id,
            shared_by_user_id=wd.shared_by_user_id,
            created_at=wd.created_at.isoformat(),
            dataset_name=wd.dataset_name,
            shared_by_user_name=wd.shared_by_user_name,
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.delete("/{workspace_id}/datasets/{dataset_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def unshare_dataset(
    workspace_id: str,
    dataset_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    try:
        service.unshare_dataset(workspace_id, user, dataset_id)
    except Exception as err:
        raise _handle_error(err) from err


@router.get("/{workspace_id}/datasets", response_model=list[SharedDatasetResponse])
def list_shared_datasets(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[SharedDatasetResponse]:
    try:
        datasets = service.list_shared_datasets(workspace_id, user)
        return [
            SharedDatasetResponse(
                id=wd.id,
                workspace_id=wd.workspace_id,
                dataset_id=wd.dataset_id,
                shared_by_user_id=wd.shared_by_user_id,
                created_at=wd.created_at.isoformat(),
                dataset_name=wd.dataset_name,
                shared_by_user_name=wd.shared_by_user_name,
            )
            for wd in datasets
        ]
    except Exception as err:
        raise _handle_error(err) from err


# -----------------------------------------------------------------------------
# SHARED CONVERSATIONS & CHAT
# -----------------------------------------------------------------------------

@router.get("/{workspace_id}/conversations", response_model=list[ConversationSummary])
def list_workspace_conversations(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> list[ConversationSummary]:
    try:
        service._require_role(workspace_id, user, min_role="viewer")
        conversations = chat_repo.list_workspace_conversations(workspace_id)
        return [
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat(),
                dataset_id=c.dataset_id,
                workspace_id=c.workspace_id,
            )
            for c in conversations
        ]
    except Exception as err:
        raise _handle_error(err) from err


# -----------------------------------------------------------------------------
# SHARED ANALYSIS RESULTS & COMMENTS
# -----------------------------------------------------------------------------

@router.post("/{workspace_id}/analysis-results", response_model=SharedAnalysisResultResponse)
def share_analysis_result(
    workspace_id: str,
    payload: ShareAnalysisResultRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> SharedAnalysisResultResponse:
    try:
        res = service.share_analysis_result(
            workspace_id=workspace_id,
            user=user,
            dataset_id=payload.dataset_id,
            question=payload.question,
            answer=payload.answer,
            metrics=payload.metrics,
            chart=payload.chart,
            insights=payload.insights,
        )
        return SharedAnalysisResultResponse(
            id=res.id,
            workspace_id=res.workspace_id,
            dataset_id=res.dataset_id,
            user_id=res.user_id,
            question=res.question,
            answer=res.answer,
            metrics_json=res.metrics_json,
            chart_json=res.chart_json,
            insights_json=res.insights_json,
            created_at=res.created_at.isoformat(),
            user_name=res.user_name,
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.get("/{workspace_id}/analysis-results", response_model=list[SharedAnalysisResultResponse])
def list_shared_analysis_results(
    workspace_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[SharedAnalysisResultResponse]:
    try:
        results = service.list_shared_analysis_results(workspace_id, user, limit)
        return [
            SharedAnalysisResultResponse(
                id=res.id,
                workspace_id=res.workspace_id,
                dataset_id=res.dataset_id,
                user_id=res.user_id,
                question=res.question,
                answer=res.answer,
                metrics_json=res.metrics_json,
                chart_json=res.chart_json,
                insights_json=res.insights_json,
                created_at=res.created_at.isoformat(),
                user_name=res.user_name,
            )
            for res in results
        ]
    except Exception as err:
        raise _handle_error(err) from err


@router.post("/{workspace_id}/analysis-results/{result_id}/comments", response_model=AnalysisCommentResponse)
def add_analysis_comment(
    workspace_id: str,
    result_id: str,
    payload: CreateCommentRequest,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> AnalysisCommentResponse:
    try:
        comment = service.add_comment(workspace_id, user, result_id=result_id, comment_text=payload.comment_text)
        return AnalysisCommentResponse(
            id=comment.id,
            result_id=comment.result_id,
            user_id=comment.user_id,
            comment_text=comment.comment_text,
            created_at=comment.created_at.isoformat(),
            user_name=comment.user_name,
        )
    except Exception as err:
        raise _handle_error(err) from err


@router.get("/{workspace_id}/analysis-results/{result_id}/comments", response_model=list[AnalysisCommentResponse])
def list_analysis_comments(
    workspace_id: str,
    result_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[AnalysisCommentResponse]:
    try:
        comments = service.list_comments(workspace_id, user, result_id)
        return [
            AnalysisCommentResponse(
                id=c.id,
                result_id=c.result_id,
                user_id=c.user_id,
                comment_text=c.comment_text,
                created_at=c.created_at.isoformat(),
                user_name=c.user_name,
            )
            for c in comments
        ]
    except Exception as err:
        raise _handle_error(err) from err


# -----------------------------------------------------------------------------
# ACTIVITY LOGS & NOTIFICATIONS
# -----------------------------------------------------------------------------

@router.get("/{workspace_id}/activity", response_model=list[ActivityLogResponse])
def list_workspace_activity(
    workspace_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[ActivityLogResponse]:
    try:
        logs = service.list_activity_logs(workspace_id, user, limit)
        return [
            ActivityLogResponse(
                id=log.id,
                workspace_id=log.workspace_id,
                user_id=log.user_id,
                event_type=log.event_type,
                metadata=log.metadata_json,  # type: ignore
                created_at=log.created_at.isoformat(),
                user_name=log.user_name,
            )
            for log in logs
        ]
    except Exception as err:
        raise _handle_error(err) from err


@notifications_router.get("", response_model=list[UserNotificationResponse])
def list_notifications(
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> list[UserNotificationResponse]:
    notifications = service.repository.list_user_notifications(user.id)
    return [
        UserNotificationResponse(
            id=n.id,
            user_id=n.user_id,
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in notifications
    ]


@notifications_router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: str,
    user: UserRecord = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service),
) -> None:
    service.repository.mark_notification_read(notification_id, user.id)

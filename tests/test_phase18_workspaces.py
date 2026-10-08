"""Comprehensive test suite for Phase 18 — Team Workspaces, Dataset Sharing & Collaboration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from analytics.database import DatabaseConfig
from backend.core.user_model import UserRecord
from backend.repositories.workspace_repository import (
    WorkspaceAccessError,
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceRepository,
)
from backend.services.workspace_service import RolePermissions, WorkspaceService


@pytest.fixture
def memory_db_config():
    return DatabaseConfig.from_environment()


@pytest.fixture
def workspace_repo(memory_db_config):
    repo = WorkspaceRepository(memory_db_config)
    repo.ensure_schema()
    return repo


@pytest.fixture
def workspace_service(workspace_repo):
    return WorkspaceService(workspace_repo)


@pytest.fixture
def user_owner():
    now = datetime.now(UTC)
    return UserRecord(
        id="user-owner-001",
        email="owner@example.com",
        name="Workspace Owner",
        password_hash="hashed",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


@pytest.fixture
def user_admin():
    now = datetime.now(UTC)
    return UserRecord(
        id="user-admin-002",
        email="admin@example.com",
        name="Workspace Admin",
        password_hash="hashed",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


@pytest.fixture
def user_analyst():
    now = datetime.now(UTC)
    return UserRecord(
        id="user-analyst-003",
        email="analyst@example.com",
        name="Workspace Analyst",
        password_hash="hashed",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


@pytest.fixture
def user_viewer():
    now = datetime.now(UTC)
    return UserRecord(
        id="user-viewer-004",
        email="viewer@example.com",
        name="Workspace Viewer",
        password_hash="hashed",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


@pytest.fixture
def user_outsider():
    now = datetime.now(UTC)
    return UserRecord(
        id="user-outsider-005",
        email="outsider@example.com",
        name="Outsider User",
        password_hash="hashed",
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


# -----------------------------------------------------------------------------
# 1. WORKSPACE CRUD & MEMBERSHIP
# -----------------------------------------------------------------------------

def test_workspace_creation(workspace_service, user_owner):
    ws = workspace_service.create_workspace(user_owner, name="IIT Jammu Analytics", description="Placement analytics team")
    assert ws.id is not None
    assert ws.name == "IIT Jammu Analytics"
    assert ws.owner_id == user_owner.id

    members = workspace_service.list_members(ws.id, user_owner)
    assert len(members) == 1
    assert members[0].user_id == user_owner.id
    assert members[0].role == RolePermissions.OWNER


def test_outsider_cannot_access_workspace(workspace_service, user_owner, user_outsider):
    ws = workspace_service.create_workspace(user_owner, name="Private Workspace")
    with pytest.raises(WorkspaceAccessError):
        workspace_service.get_workspace(ws.id, user_outsider)
    with pytest.raises(WorkspaceAccessError):
        workspace_service.list_members(ws.id, user_outsider)


# -----------------------------------------------------------------------------
# 2. INVITATION & ROLE MANAGEMENT
# -----------------------------------------------------------------------------

def test_invitation_flow(workspace_service, user_owner, user_analyst):
    ws = workspace_service.create_workspace(user_owner, name="Shared Workspace")

    inv, raw_token = workspace_service.create_invitation(
        workspace_id=ws.id,
        inviter=user_owner,
        invitee_email=user_analyst.email,
        role=RolePermissions.ANALYST,
    )
    assert inv.invitee_email == user_analyst.email
    assert raw_token is not None

    mem = workspace_service.accept_invitation(raw_token, user_analyst)
    assert mem.workspace_id == ws.id
    assert mem.user_id == user_analyst.id
    assert mem.role == RolePermissions.ANALYST

    # Cannot re-accept accepted invitation
    with pytest.raises(WorkspaceConflictError):
        workspace_service.accept_invitation(raw_token, user_analyst)


def test_role_based_permissions(workspace_service, user_owner, user_admin, user_analyst, user_viewer):
    ws = workspace_service.create_workspace(user_owner, name="Role Test Workspace")

    # Add members directly
    workspace_service.repository.add_member(ws.id, user_admin.id, role=RolePermissions.ADMIN)
    workspace_service.repository.add_member(ws.id, user_analyst.id, role=RolePermissions.ANALYST)
    workspace_service.repository.add_member(ws.id, user_viewer.id, role=RolePermissions.VIEWER)

    # Viewer cannot invite members
    with pytest.raises(WorkspaceAccessError):
        workspace_service.create_invitation(ws.id, inviter=user_viewer, invitee_email="new@example.com")

    # Analyst cannot invite members
    with pytest.raises(WorkspaceAccessError):
        workspace_service.create_invitation(ws.id, inviter=user_analyst, invitee_email="new@example.com")

    # Admin can invite members
    inv, _ = workspace_service.create_invitation(ws.id, inviter=user_admin, invitee_email="new@example.com")
    assert inv.role == RolePermissions.ANALYST


# -----------------------------------------------------------------------------
# 3. DATASET SHARING & ACCESS CONTROL
# -----------------------------------------------------------------------------

def test_dataset_sharing(workspace_service, user_owner, user_analyst, user_viewer):
    ws = workspace_service.create_workspace(user_owner, name="Dataset Sharing Workspace")
    workspace_service.repository.add_member(ws.id, user_analyst.id, role=RolePermissions.ANALYST)
    workspace_service.repository.add_member(ws.id, user_viewer.id, role=RolePermissions.VIEWER)

    # Analyst shares dataset
    wd = workspace_service.share_dataset(ws.id, user_analyst, dataset_id="ds_placement_100")
    assert wd.dataset_id == "ds_placement_100"

    # Viewer can view shared datasets list
    shared = workspace_service.list_shared_datasets(ws.id, user_viewer)
    assert len(shared) == 1
    assert shared[0].dataset_id == "ds_placement_100"

    # Viewer cannot unshare dataset
    with pytest.raises(WorkspaceAccessError):
        workspace_service.unshare_dataset(ws.id, user_viewer, dataset_id="ds_placement_100")


# -----------------------------------------------------------------------------
# 4. ANALYSIS RESULT SHARING & COMMENTS
# -----------------------------------------------------------------------------

def test_shared_analysis_results_and_comments(workspace_service, user_owner, user_analyst, user_viewer):
    ws = workspace_service.create_workspace(user_owner, name="Analytics Collaboration")
    workspace_service.repository.add_member(ws.id, user_analyst.id, role=RolePermissions.ANALYST)
    workspace_service.repository.add_member(ws.id, user_viewer.id, role=RolePermissions.VIEWER)

    # Viewer cannot post shared analysis result
    with pytest.raises(WorkspaceAccessError):
        workspace_service.share_analysis_result(
            ws.id, user=user_viewer, dataset_id="ds_1", question="Rate?", answer="72%"
        )

    # Analyst shares analysis result
    res = workspace_service.share_analysis_result(
        ws.id, user=user_analyst, dataset_id="ds_1", question="What is placement rate?", answer="72%"
    )
    assert res.question == "What is placement rate?"

    # Viewer adds comment to result
    comment = workspace_service.add_comment(ws.id, user=user_viewer, result_id=res.id, comment_text="Verified with team")
    assert comment.comment_text == "Verified with team"
    assert comment.user_id == user_viewer.id


# -----------------------------------------------------------------------------
# 5. OWNERSHIP TRANSFER & DELETION
# -----------------------------------------------------------------------------

def test_ownership_transfer(workspace_service, user_owner, user_admin):
    ws = workspace_service.create_workspace(user_owner, name="Transfer Workspace")
    workspace_service.repository.add_member(ws.id, user_admin.id, role=RolePermissions.ADMIN)

    # Admin cannot transfer ownership
    with pytest.raises(WorkspaceAccessError):
        workspace_service.transfer_ownership(ws.id, current_owner=user_admin, new_owner_user_id=user_admin.id)

    # Owner transfers ownership to admin
    updated_ws = workspace_service.transfer_ownership(ws.id, current_owner=user_owner, new_owner_user_id=user_admin.id)
    assert updated_ws.owner_id == user_admin.id

    # Former owner is now admin
    former_owner_mem = workspace_service.repository.get_member(ws.id, user_owner.id)
    assert former_owner_mem.role == RolePermissions.ADMIN

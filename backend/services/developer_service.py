"""Developer API keys and outbound webhook security/services."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import BackgroundTasks, Request

from backend.core.config import settings
from backend.core.user_model import UserRecord
from backend.repositories.developer_repository import DeveloperRepository
from backend.repositories.user_repository import UserRepository, UserNotFoundError
from backend.repositories.workspace_repository import WorkspaceAccessError, WorkspaceRepository
from backend.services.billing_service import BillingService
from backend.services.workspace_service import RolePermissions, WorkspaceService


API_SCOPES = frozenset({
    "datasets:read", "datasets:write", "analytics:read", "analytics:run",
    "analytics:question", "reports:read", "workspace:read", "webhooks:read", "webhooks:write",
})
WEBHOOK_EVENTS = frozenset({
    "dataset.created", "dataset.updated", "dataset.deleted",
    "analytics.completed", "analytics.failed", "report.created",
    "workspace.member_added", "workspace.member_removed",
    "subscription.updated", "subscription.canceled", "usage.limit_reached",
    "security.event", "webhook.test",
})
_RATE_LIMITS = {"free": 100, "pro": 1000, "team": 5000, "enterprise": 10000}
_ANALYTICS_RATE_FACTOR = 5


class DeveloperAPIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class DeveloperAPIContext:
    api_key_id: str
    user: UserRecord
    workspace_id: str
    scopes: frozenset[str]
    role: str

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise DeveloperAPIError(403, "INSUFFICIENT_SCOPE", "The API key does not have the required permission.")
        if scope in {"analytics:run", "analytics:question", "datasets:write"} and not RolePermissions.can_analyze(self.role):
            raise DeveloperAPIError(403, "WORKSPACE_PERMISSION_CHANGED", "Current workspace permissions do not allow this operation.")


class DeveloperAPIService:
    def __init__(self, repository: DeveloperRepository, users: UserRepository, workspaces: WorkspaceRepository, billing: BillingService) -> None:
        self.repository = repository
        self.users = users
        self.workspaces = workspaces
        self.billing = billing
        self.workspace_service = WorkspaceService(workspaces)

    def _require_developer_feature(self, workspace_id: str) -> None:
        if not self.billing.has_feature(workspace_id, "developer_api"):
            raise DeveloperAPIError(403, "FEATURE_NOT_AVAILABLE", "Developer API access is not available on this workspace plan.")
        subscription = self.billing.repository.get_subscription_for_workspace(workspace_id)
        if subscription and subscription.status not in {"active", "trialing"}:
            raise DeveloperAPIError(403, "SUBSCRIPTION_INACTIVE", "The workspace subscription does not allow developer API access.")

    def _require_key_admin(self, workspace_id: str, user: UserRecord) -> str:
        try:
            role = self.workspace_service._require_role(workspace_id, user, min_role=RolePermissions.ADMIN)
        except WorkspaceAccessError as error:
            raise DeveloperAPIError(403, "FORBIDDEN", "Workspace administrator permission is required.") from error
        if not RolePermissions.can_manage_security(role):
            raise DeveloperAPIError(403, "FORBIDDEN", "Workspace security-management permission is required.")
        self._require_developer_feature(workspace_id)
        return role

    def create_key(self, *, user: UserRecord, workspace_id: str, name: str, scopes: list[str], expires_at: datetime | None = None, rotated_from_id: str | None = None) -> dict[str, Any]:
        self._require_key_admin(workspace_id, user)
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 128:
            raise DeveloperAPIError(422, "INVALID_KEY_NAME", "API key name must be between 1 and 128 characters.")
        if not scopes or len(scopes) != len(set(scopes)) or not set(scopes).issubset(API_SCOPES):
            raise DeveloperAPIError(422, "INVALID_SCOPES", "Select one or more supported API scopes.")
        expiry = None
        if expires_at:
            expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc):
                raise DeveloperAPIError(422, "INVALID_EXPIRATION", "Expiration must be in the future.")
        mode = "live" if settings.app_env == "production" else "test"
        raw_key = f"ask_{mode}_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:24]
        key_record = self.repository.create_api_key(
            user_id=user.id, workspace_id=workspace_id, name=normalized_name, key_prefix=key_prefix,
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(), scopes=sorted(scopes),
            expires_at=expiry.astimezone(timezone.utc).isoformat() if expiry else None,
            rotated_from_id=rotated_from_id,
        )
        self._audit(workspace_id, user.id, "api_key_created", {"api_key_id": key_record["id"], "scopes": sorted(scopes)})
        return {**self._public_key(key_record), "api_key": raw_key}

    def list_keys(self, user: UserRecord, workspace_id: str) -> list[dict[str, Any]]:
        self._require_key_admin(workspace_id, user)
        return [self._public_key(record) for record in self.repository.list_api_keys(workspace_id)]

    def revoke_key(self, user: UserRecord, workspace_id: str, key_id: str) -> None:
        self._require_key_admin(workspace_id, user)
        record = self.repository.get_api_key(key_id, workspace_id)
        if record is None:
            raise DeveloperAPIError(404, "API_KEY_NOT_FOUND", "API key was not found.")
        self.repository.revoke_api_key(key_id, workspace_id)
        self._audit(workspace_id, user.id, "api_key_revoked", {"api_key_id": key_id})

    def rotate_key(self, user: UserRecord, workspace_id: str, key_id: str, grace_seconds: int = 0) -> dict[str, Any]:
        self._require_key_admin(workspace_id, user)
        if not 0 <= grace_seconds <= 86400:
            raise DeveloperAPIError(422, "INVALID_ROTATION_GRACE", "Rotation grace must be between 0 and 86400 seconds.")
        previous = self.repository.get_api_key(key_id, workspace_id)
        if previous is None or previous["revoked_at"]:
            raise DeveloperAPIError(404, "API_KEY_NOT_FOUND", "Active API key was not found.")
        expiry = datetime.now(timezone.utc) + timedelta(seconds=grace_seconds) if grace_seconds else None
        replacement = self.create_key(
            user=user, workspace_id=workspace_id, name=previous["name"], scopes=previous["scopes"],
            expires_at=datetime.fromisoformat(previous["expires_at"]) if previous["expires_at"] else None,
            rotated_from_id=key_id,
        )
        if expiry:
            old_expiry = datetime.fromisoformat(previous["expires_at"]) if previous["expires_at"] else None
            if old_expiry is None or expiry < old_expiry:
                self.repository.set_key_expiry(key_id, workspace_id, expiry.isoformat())
        else:
            self.repository.revoke_api_key(key_id, workspace_id)
        self._audit(workspace_id, user.id, "api_key_rotated", {"old_api_key_id": key_id, "new_api_key_id": replacement["id"], "grace_seconds": grace_seconds})
        return {**replacement, "old_key_expires_at": expiry.isoformat() if expiry else None}

    def authenticate(self, request: Request, raw_key: str) -> DeveloperAPIContext:
        request.state.developer_api_key_id = None
        expected_prefix = "ask_live_" if settings.app_env == "production" else "ask_test_"
        if not raw_key.startswith(expected_prefix):
            raise DeveloperAPIError(401, "INVALID_API_KEY", "API key is invalid or inactive.")
        key_prefix = raw_key[:24]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        record = next((candidate for candidate in self.repository.find_api_keys_by_prefix(key_prefix) if hmac.compare_digest(candidate["key_hash"], key_hash)), None)
        if record is None or record["revoked_at"]:
            raise DeveloperAPIError(401, "INVALID_API_KEY", "API key is invalid or inactive.")
        if record["expires_at"]:
            expires = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00"))
            if expires <= datetime.now(timezone.utc):
                raise DeveloperAPIError(401, "API_KEY_EXPIRED", "API key has expired.")
        try:
            user = self.users.get_by_id(record["user_id"])
        except UserNotFoundError as error:
            raise DeveloperAPIError(401, "INVALID_API_KEY", "API key owner is unavailable.") from error
        if not user.is_active or self.workspaces.get_member(record["workspace_id"], user.id) is None:
            raise DeveloperAPIError(401, "API_KEY_INACTIVE", "API key owner no longer has workspace access.")
        self._require_developer_feature(record["workspace_id"])
        try:
            role = self.workspace_service._require_role(record["workspace_id"], user, min_role=RolePermissions.VIEWER)
        except WorkspaceAccessError as error:
            raise DeveloperAPIError(401, "API_KEY_INACTIVE", "API key owner no longer has workspace access.") from error
        context = DeveloperAPIContext(record["id"], user, record["workspace_id"], frozenset(record["scopes"]), role)
        request.state.developer_api_key_id = record["id"]
        request.state.developer_api_user_id = user.id
        request.state.developer_api_workspace_id = record["workspace_id"]
        self._enforce_rate_limit(request, context)
        self.repository.set_key_last_used(record["id"], datetime.now(timezone.utc).isoformat())
        return context

    def _enforce_rate_limit(self, request: Request, context: DeveloperAPIContext) -> None:
        plan = self.billing.get_plan_for_workspace(context.workspace_id)
        hourly_limit = _RATE_LIMITS.get(plan.plan_id, _RATE_LIMITS["free"])
        endpoint_class = "analytics" if "/analytics/" in request.url.path else "standard"
        if endpoint_class == "analytics":
            hourly_limit = max(1, hourly_limit // _ANALYTICS_RATE_FACTOR)
        now = datetime.now(timezone.utc)
        window_start = now.replace(minute=0, second=0, microsecond=0)
        window_key = window_start.strftime("%Y%m%d%H")
        workspace_bucket = f"workspace:{context.workspace_id}:{endpoint_class}:{window_key}"
        key_bucket = f"key:{context.api_key_id}:{endpoint_class}:{window_key}"
        workspace_count = self.repository.increment_rate_bucket(bucket_key=workspace_bucket, workspace_id=context.workspace_id, api_key_id=context.api_key_id, endpoint_class=endpoint_class, window_start=window_start.isoformat())
        key_count = self.repository.increment_rate_bucket(bucket_key=key_bucket, workspace_id=context.workspace_id, api_key_id=context.api_key_id, endpoint_class=endpoint_class, window_start=window_start.isoformat())
        used = max(workspace_count, key_count)
        remaining = max(hourly_limit - used, 0)
        reset = int((window_start + timedelta(hours=1)).timestamp())
        request.state.developer_rate_headers = {"X-RateLimit-Limit": str(hourly_limit), "X-RateLimit-Remaining": str(remaining), "X-RateLimit-Reset": str(reset)}
        if used > hourly_limit:
            raise DeveloperAPIError(429, "RATE_LIMITED", "The API request limit for this workspace or key has been reached.")

    @staticmethod
    def _public_key(record: dict[str, Any]) -> dict[str, Any]:
        return {key: record.get(key) for key in ("id", "user_id", "workspace_id", "name", "key_prefix", "scopes", "created_at", "expires_at", "last_used_at", "revoked_at", "rotated_from_id")}

    def record_request(self, request: Request, status_code: int, duration_ms: int, request_id: str) -> None:
        api_key_id = getattr(request.state, "developer_api_key_id", None)
        user_id = getattr(request.state, "developer_api_user_id", None)
        workspace_id = getattr(request.state, "developer_api_workspace_id", None)
        self.repository.record_api_usage(
            api_key_id=api_key_id,
            user_id=user_id,
            workspace_id=workspace_id,
            endpoint=request.url.path, method=request.method, http_status=status_code,
            response_time_ms=duration_ms, request_id=request_id,
        )
        if workspace_id and user_id and status_code in {403, 429}:
            event_type = "api_scope_violation" if status_code == 403 else "api_rate_limit_event"
            self.workspaces.log_activity(workspace_id, user_id, event_type, {"api_key_id": api_key_id, "endpoint": request.url.path, "status": status_code})

    def usage(self, user: UserRecord, workspace_id: str, since: str) -> dict[str, Any]:
        self._require_key_admin(workspace_id, user)
        return self.repository.usage_summary(workspace_id, since)

    def _audit(self, workspace_id: str, user_id: str, event_type: str, metadata: dict[str, Any]) -> None:
        self.workspaces.log_activity(workspace_id, user_id, event_type, metadata)


class WebhookService:
    def __init__(self, repository: DeveloperRepository, workspaces: WorkspaceRepository) -> None:
        self.repository = repository
        self.workspaces = workspaces

    def _cipher(self) -> Fernet:
        key = settings.webhook_encryption_key
        if not key:
            raise DeveloperAPIError(503, "WEBHOOK_ENCRYPTION_UNCONFIGURED", "Webhook secret encryption is not configured.")
        try:
            return Fernet(key.encode())
        except (ValueError, TypeError) as error:
            raise DeveloperAPIError(503, "WEBHOOK_ENCRYPTION_INVALID", "Webhook secret encryption configuration is invalid.") from error

    @staticmethod
    def validate_url(url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise DeveloperAPIError(422, "INVALID_WEBHOOK_URL", "Webhook URL must be HTTPS and cannot include credentials, a query, or a fragment.")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain", "metadata.google.internal", "metadata.azure.internal"} or host.endswith((".local", ".internal", ".localhost")):
            raise DeveloperAPIError(422, "WEBHOOK_SSRF_BLOCKED", "Webhook URL targets a reserved host.")
        try:
            addresses = [ipaddress.ip_address(host)] if _is_ip(host) else [ipaddress.ip_address(result[4][0]) for result in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)]
        except (OSError, ValueError) as error:
            raise DeveloperAPIError(422, "WEBHOOK_DNS_FAILED", "Webhook host could not be resolved safely.") from error
        if not addresses or any(not address.is_global for address in addresses):
            raise DeveloperAPIError(422, "WEBHOOK_SSRF_BLOCKED", "Webhook URL resolves to a private or reserved network.")
        if parsed.port not in (None, 443):
            raise DeveloperAPIError(422, "INVALID_WEBHOOK_URL", "Webhook URLs must use the standard HTTPS port.")
        return url.strip()

    def create(self, *, user: UserRecord, workspace_id: str, url: str, description: str | None, events: list[str]) -> dict[str, Any]:
        safe_url = self.validate_url(url)
        self._validate_events(events)
        secret = secrets.token_urlsafe(32)
        encrypted = self._cipher().encrypt(secret.encode()).decode()
        record = self.repository.create_webhook(user_id=user.id, workspace_id=workspace_id, url=safe_url, description=description, secret_ciphertext=encrypted, events=sorted(set(events)))
        self.workspaces.log_activity(workspace_id, user.id, "webhook_created", {"webhook_id": record["id"], "events": sorted(set(events))})
        return {**self._public_webhook(record), "secret": secret}

    def list(self, workspace_id: str) -> list[dict[str, Any]]:
        return [self._public_webhook(record) for record in self.repository.list_webhooks(workspace_id)]

    def update(self, *, user: UserRecord, workspace_id: str, webhook_id: str, url: str | None = None, description: str | None = None, events: list[str] | None = None, active: bool | None = None) -> dict[str, Any]:
        if self.repository.get_webhook(webhook_id, workspace_id) is None:
            raise DeveloperAPIError(404, "WEBHOOK_NOT_FOUND", "Webhook was not found.")
        if url is not None:
            url = self.validate_url(url)
        if events is not None:
            self._validate_events(events)
        self.repository.update_webhook(webhook_id, workspace_id, url=url, description=description, events=events, active=active)
        self.workspaces.log_activity(workspace_id, user.id, "webhook_updated", {"webhook_id": webhook_id})
        return self._public_webhook(self.repository.get_webhook(webhook_id, workspace_id))

    def rotate_secret(self, user: UserRecord, workspace_id: str, webhook_id: str) -> dict[str, Any]:
        current = self.repository.get_webhook(webhook_id, workspace_id)
        if current is None:
            raise DeveloperAPIError(404, "WEBHOOK_NOT_FOUND", "Webhook was not found.")
        secret = secrets.token_urlsafe(32)
        encrypted = self._cipher().encrypt(secret.encode()).decode()
        self.repository.update_webhook(webhook_id, workspace_id, secret_ciphertext=encrypted)
        self.workspaces.log_activity(workspace_id, user.id, "webhook_secret_rotated", {"webhook_id": webhook_id})
        return {**self._public_webhook(self.repository.get_webhook(webhook_id, workspace_id)), "secret": secret}

    def delete(self, user: UserRecord, workspace_id: str, webhook_id: str) -> None:
        if self.repository.get_webhook(webhook_id, workspace_id) is None:
            raise DeveloperAPIError(404, "WEBHOOK_NOT_FOUND", "Webhook was not found.")
        self.repository.delete_webhook(webhook_id, workspace_id)
        self.workspaces.log_activity(workspace_id, user.id, "webhook_deleted", {"webhook_id": webhook_id})

    def list_deliveries(self, workspace_id: str, webhook_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self.repository.get_webhook(webhook_id, workspace_id) is None:
            raise DeveloperAPIError(404, "WEBHOOK_NOT_FOUND", "Webhook was not found.")
        return self.repository.list_deliveries(webhook_id, workspace_id, limit)

    def emit_event(self, workspace_id: str, event_type: str, payload: dict[str, Any], background_tasks: BackgroundTasks | None = None, *, event_id: str | None = None) -> int:
        if event_type not in WEBHOOK_EVENTS:
            return 0
        normalized_event_id = event_id or str(uuid4())
        event_payload = {"id": normalized_event_id, "type": event_type, "created_at": datetime.now(timezone.utc).isoformat(), "workspace_id": workspace_id, "data": payload}
        queued = 0
        for webhook in self.repository.list_active_webhooks(workspace_id, event_type):
            delivery_id = self.repository.create_delivery(webhook_id=webhook["id"], workspace_id=workspace_id, event_id=normalized_event_id, event_type=event_type, payload=event_payload)
            if delivery_id is None:
                continue
            queued += 1
            if background_tasks is None:
                self.deliver(delivery_id)
            else:
                background_tasks.add_task(self.deliver, delivery_id)
        return queued

    def deliver(self, delivery_id: str) -> None:
        delivery = self.repository.get_delivery(delivery_id)
        if delivery is None:
            return
        webhook = self.repository.get_webhook(delivery["webhook_id"], delivery["workspace_id"])
        if webhook is None or not webhook["active"]:
            self.repository.finish_delivery(delivery_id, status="failed", response_code=None, duration_ms=0, attempt_count=0, last_error_code="webhook_inactive")
            return
        try:
            self.validate_url(webhook["url"])
            secret = self._cipher().decrypt(webhook["secret_ciphertext"].encode())
        except (DeveloperAPIError, InvalidToken):
            self.repository.finish_delivery(delivery_id, status="failed", response_code=None, duration_ms=0, attempt_count=0, last_error_code="webhook_configuration_invalid")
            return

        body = json.dumps(delivery["payload"], separators=(",", ":"), sort_keys=True).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        response_code = None
        last_error = "delivery_failed"
        elapsed_ms = 0
        for attempt in range(1, 4):
            started = time.perf_counter()
            try:
                response = httpx.post(
                    webhook["url"], content=body, timeout=5.0, follow_redirects=False, trust_env=False,
                    headers={
                        "Content-Type": "application/json",
                        "X-AskMyData-Signature": f"t={timestamp},v1={signature}",
                        "X-AskMyData-Event": delivery["event_type"],
                        "X-AskMyData-Delivery-ID": delivery["id"],
                        "X-AskMyData-Timestamp": timestamp,
                    },
                )
                response_code = response.status_code
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                if 200 <= response.status_code < 300:
                    self.repository.finish_delivery(delivery_id, status="succeeded", response_code=response_code, duration_ms=elapsed_ms, attempt_count=attempt, last_error_code=None)
                    return
                last_error = "remote_http_error"
            except httpx.TimeoutException:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                last_error = "timeout"
            except httpx.HTTPError:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                last_error = "transport_error"
            if attempt < 3:
                time.sleep(0.25 * (2 ** (attempt - 1)))
        self.repository.finish_delivery(delivery_id, status="failed", response_code=response_code, duration_ms=elapsed_ms, attempt_count=3, last_error_code=last_error)

    @staticmethod
    def _validate_events(events: list[str]) -> None:
        if not events or len(events) != len(set(events)) or not set(events).issubset(WEBHOOK_EVENTS):
            raise DeveloperAPIError(422, "INVALID_WEBHOOK_EVENTS", "Select supported webhook event types.")

    @staticmethod
    def _public_webhook(record: dict[str, Any]) -> dict[str, Any]:
        return {key: record.get(key) for key in ("id", "user_id", "workspace_id", "url", "description", "events", "active", "created_at", "updated_at", "last_delivery_at", "failure_count")}


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .common import APIModel


class APIKeyCreateRequest(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    scopes: list[str] = Field(min_length=1, max_length=9)
    expires_at: datetime | None = None


class APIKeyRotateRequest(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    grace_seconds: int = Field(default=0, ge=0, le=86400)


class WebhookCreateRequest(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    url: str = Field(min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] = Field(min_length=1, max_length=13)


class WebhookUpdateRequest(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=255)
    events: list[str] | None = Field(default=None, min_length=1, max_length=13)
    active: bool | None = None


class PublicQuestionRequest(APIModel):
    dataset_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=2000)


class PublicSuccess(APIModel):
    success: bool = True
    data: Any
    request_id: str
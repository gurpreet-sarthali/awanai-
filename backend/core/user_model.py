"""Authenticated user record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class UserRecord:
    id: str
    email: str
    name: str
    password_hash: str | None
    google_id: str | None = None
    google_access_token: str | None = None
    google_refresh_token: str | None = None
    profile_picture_url: str | None = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    def public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "profile_picture_url": self.profile_picture_url,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

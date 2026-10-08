"""Registration, login, and token issuance."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import jwt

from backend.core.config import settings
from backend.core.security import create_access_token, hash_password, verify_password
from backend.core.user_model import UserRecord
from backend.repositories.user_repository import UserConflictError, UserNotFoundError, UserRepository


class AuthenticationError(ValueError):
    pass


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    def register(self, *, email: str, name: str, password: str) -> tuple[UserRecord, str]:
        if len(password) < 4:
            raise AuthenticationError("Password must be at least 4 characters.")
        if "@" not in email:
            raise AuthenticationError("A valid email address is required.")
        try:
            user = self.users.create_user(email=email, name=name, password_hash=hash_password(password))
        except UserConflictError as error:
            raise AuthenticationError(str(error)) from error
        return user, self.issue_token(user)

    def login(self, *, email: str, password: str) -> tuple[UserRecord, str]:
        try:
            user = self.users.get_by_email(email)
        except UserNotFoundError as error:
            raise AuthenticationError("Invalid email or password.") from error
        if not user.is_active or not user.password_hash or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        self.users.touch_login(user.id)
        return user, self.issue_token(user)

    def resolve_token(self, token: str) -> UserRecord:
        try:
            from backend.core.security import decode_access_token

            decoded = decode_access_token(token, secret=settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
            user = self.users.get_by_id(str(decoded["sub"]))
        except (jwt.PyJWTError, UserNotFoundError, KeyError) as error:
            raise AuthenticationError("Invalid or expired authentication token.") from error
        if not user.is_active:
            raise AuthenticationError("This account is inactive.")
        return user

    def issue_token(self, user: UserRecord) -> str:
        return create_access_token(
            subject=user.id,
            secret=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            expires_minutes=settings.access_token_expire_minutes,
        )

    def google_login_url(self) -> str:
        if any(
            not value or value.strip().startswith("YOUR_")
            for value in (settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri)
        ):
            raise AuthenticationError("Google OAuth is not configured.")
        state = self._generate_oauth_state()
        scope = "openid email profile https://www.googleapis.com/auth/drive.file"
        params = urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": settings.google_redirect_uri,
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
                "scope": scope,
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    def _generate_oauth_state(self) -> str:
        """Generate a time-limited CSRF state token."""
        nonce = secrets.token_urlsafe(16)
        timestamp = str(int(time.time()))
        payload = f"{nonce}.{timestamp}"
        signature = hmac.new(
            settings.oauth_state_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{signature}"

    def validate_oauth_state(self, state: str, max_age_seconds: int = 600) -> None:
        """Verify CSRF state token. Raises AuthenticationError on failure."""
        try:
            parts = state.split(".")
            if len(parts) != 3:
                raise AuthenticationError("Invalid OAuth state.")
            nonce, timestamp, provided_sig = parts
            age = int(time.time()) - int(timestamp)
            if age < 0 or age > max_age_seconds:
                raise AuthenticationError("OAuth state has expired. Please try again.")
            payload = f"{nonce}.{timestamp}"
            expected_sig = hmac.new(
                settings.oauth_state_secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_sig, provided_sig):
                raise AuthenticationError("Invalid OAuth state signature.")
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("Malformed OAuth state.") from exc

    def handle_google_callback(self, code: str, state: str) -> tuple[UserRecord, str, dict[str, Any]]:
        if any(
            not value or value.strip().startswith("YOUR_")
            for value in (settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri)
        ):
            raise AuthenticationError("Google OAuth is not configured.")
        self.validate_oauth_state(state)

        import httpx
        try:
            token_resp = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri,
                },
                timeout=10.0,
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            if not access_token:
                raise AuthenticationError("Google did not return an access token.")

            user_info_resp = httpx.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            user_info_resp.raise_for_status()
            user_info = user_info_resp.json()
        except AuthenticationError:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise AuthenticationError("Google authentication could not be completed.") from error

        email = str(user_info.get("email", "")).lower().strip()
        google_id = str(user_info.get("id", "")).strip()
        if not email or not google_id or user_info.get("verified_email") is not True:
            raise AuthenticationError("Google must provide a verified email address.")
        name = user_info.get("name") or email.split("@")[0]
        picture = user_info.get("picture")

        try:
            user = self.users.get_by_email(email)
            if not user.is_active:
                raise AuthenticationError("This account is inactive.")
            if user.google_id and user.google_id != google_id:
                raise AuthenticationError("This email is linked to a different Google account.")
            if not user.google_id:
                self.users.update_google_id(user.id, google_id)
        except UserNotFoundError:
            user = self.users.create_user(email=email, name=name, password_hash=None, google_id=google_id, profile_picture_url=picture)

        refresh_token = tokens.get("refresh_token")
        self.users.update_google_tokens(user.id, access_token, refresh_token)

        self.users.touch_login(user.id)
        return user, self.issue_token(user), tokens

    def refresh_google_token(self, user_id: str) -> str:
        import httpx
        user = self.users.get_by_id(user_id)
        if not user.google_refresh_token:
            raise AuthenticationError("User does not have a Google refresh token.")
            
        token_resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": user.google_refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10.0,
        )
        if token_resp.status_code != 200:
            raise AuthenticationError("Failed to refresh Google OAuth token.")
            
        tokens = token_resp.json()
        access_token = tokens["access_token"]
        new_refresh = tokens.get("refresh_token")
        
        self.users.update_google_tokens(user.id, access_token, new_refresh)
        return access_token

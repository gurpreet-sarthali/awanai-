from typing import Annotated
from fastapi import APIRouter, Depends, Request

from backend.api.dependencies import get_auth_service, get_current_user, get_monitoring_service
from backend.core.config import settings
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.schemas.auth import (
    AuthTokenResponse,
    AuthUserResponse,
    GoogleAuthStatusResponse,
    GoogleCallbackRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
)
from backend.services.auth_service import AuthenticationError, AuthService
from backend.services.monitoring_service import MonitoringService
from backend.services.rate_limiter import AIRateLimitError, LoginAttemptLimiter

router = APIRouter(prefix="/auth", tags=["authentication"])
_login_attempt_limiter = LoginAttemptLimiter(settings.max_login_attempts)


def _user_response(user: UserRecord) -> AuthUserResponse:
    return AuthUserResponse(**user.public_dict())


def _token_response(user: UserRecord, token: str) -> AuthTokenResponse:
    return AuthTokenResponse(access_token=token, user=_user_response(user))


@router.post("/register", response_model=AuthTokenResponse, summary="Register a local user account")
def register(
    request: RegisterRequest,
    req: Request,
    service: AuthService = Depends(get_auth_service),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> AuthTokenResponse:
    try:
        user, token = service.register(email=request.email, name=request.name, password=request.password)
        monitoring_service.track_event(user.id, "account_created", {"email": user.email})
        monitoring_service.start_user_session(user.id, req.client.host if req.client else None, req.headers.get("user-agent"))
        return _token_response(user, token)
    except AuthenticationError as error:
        monitoring_service.track_event(None, "account_creation_failed", {"email": request.email})
        raise AppError(400, "registration_failed", str(error)) from error


@router.post("/login", response_model=AuthTokenResponse, summary="Login with email and password")
def login(
    request: LoginRequest,
    req: Request,
    service: AuthService = Depends(get_auth_service),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> AuthTokenResponse:
    client_ip = req.client.host if req.client else "unknown"
    attempt_key = f"{request.email.strip().lower()}:{client_ip}"
    try:
        _login_attempt_limiter.check(attempt_key)
    except AIRateLimitError as error:
        raise AppError(429, "login_rate_limit", str(error)) from error

    try:
        user, token = service.login(email=request.email, password=request.password)
        _login_attempt_limiter.reset(attempt_key)
        monitoring_service.track_event(user.id, "login", {"method": "password"})
        monitoring_service.start_user_session(user.id, req.client.host if req.client else None, req.headers.get("user-agent"))
        return _token_response(user, token)
    except AuthenticationError as error:
        _login_attempt_limiter.record_failure(attempt_key)
        monitoring_service.track_event(None, "login_failed", {"email": request.email})
        raise AppError(401, "authentication_failed", str(error)) from error


@router.post("/logout", response_model=MessageResponse, summary="Logout current client session")
def logout(
    user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> MessageResponse:
    monitoring_service.track_event(user.id, "logout")
    return MessageResponse(message="Logout successful. Discard the client-side access token.")


@router.get("/me", response_model=AuthUserResponse, summary="Get the current authenticated user")
def me(user: UserRecord = Depends(get_current_user)) -> AuthUserResponse:
    return _user_response(user)


@router.get("/google/status", response_model=GoogleAuthStatusResponse, summary="Google OAuth configuration status")
def google_status(service: AuthService = Depends(get_auth_service)) -> GoogleAuthStatusResponse:
    try:
        return GoogleAuthStatusResponse(configured=True, authorization_url=service.google_login_url())
    except AuthenticationError:
        return GoogleAuthStatusResponse(configured=False, authorization_url=None)


@router.post("/google/callback", response_model=AuthTokenResponse, summary="Handle Google OAuth callback")
def google_callback(
    request: GoogleCallbackRequest,
    req: Request,
    service: AuthService = Depends(get_auth_service),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> AuthTokenResponse:
    try:
        user, token, _ = service.handle_google_callback(request.code, request.state)
        monitoring_service.track_event(user.id, "login", {"method": "google_oauth"})
        monitoring_service.start_user_session(user.id, req.client.host if req.client else None, req.headers.get("user-agent"))
        return _token_response(user, token)
    except AuthenticationError as error:
        monitoring_service.track_event(None, "login_failed", {"method": "google_oauth"})
        raise AppError(401, "authentication_failed", str(error)) from error

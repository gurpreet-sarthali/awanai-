"""
AwanAI Visitor Registration Route.

POST /api/v1/visitors/register

Accepts a self-reported name and email, saves them to Supabase via the
backend service (using the service-role key, which never touches the frontend),
issues a temporary session token for seamless dashboard access,
and returns the visitor session details.

Rate limiting: 10 requests per minute per IP (simple in-memory window).

SECURITY NOTE:
- The email is NOT verified. Do not use it as proof of identity.
- The service-role key is held server-side only.
- RLS on the visitors table prevents anon clients from reading other records.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Request

from backend.api.dependencies import get_auth_service
from backend.exceptions.handlers import AppError
from backend.schemas.visitor import VisitorRegisterRequest, VisitorRegisterResponse
from backend.services.auth_service import AuthService
from backend.services.visitor_service import VisitorServiceError, register_or_update_visitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/visitors", tags=["visitors"])

# --------------------------------------------------------------------------- #
#  Simple in-memory rate limiter (10 requests / 60 s per IP)                  #
# --------------------------------------------------------------------------- #
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 10
_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    """Raise AppError 429 if the IP has exceeded the rate limit."""
    now = time.monotonic()
    window_start = now - _RATE_WINDOW_SECONDS
    hits = _rate_store[ip]
    # Evict timestamps outside the window
    _rate_store[ip] = [t for t in hits if t > window_start]
    if len(_rate_store[ip]) >= _RATE_MAX_REQUESTS:
        raise AppError(429, "rate_limit_exceeded", "Too many requests. Please wait a moment.")
    _rate_store[ip].append(now)


@router.post(
    "/register",
    response_model=VisitorRegisterResponse,
    summary="Register or update an AwanAI visitor (unverified name/email)",
)
def register_visitor(
    body: VisitorRegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> VisitorRegisterResponse:
    """
    Register a new visitor or refresh a returning visitor's record.

    The email is self-reported and NOT verified. A temporary session JWT is
    issued to allow session preservation, dataset isolation, and analytics access.

    Returns HTTP 200 on success (for both new and returning visitors).
    Returns HTTP 429 if the rate limit is exceeded.
    Returns HTTP 503 if the registration backend is unavailable.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Sanitise inputs beyond Pydantic validation
    clean_name = " ".join(body.name.strip().split())  # collapse whitespace
    clean_email = body.email.strip().lower()

    if len(clean_name) < 2:
        raise AppError(400, "invalid_name", "Name must be at least 2 characters.")

    try:
        result = register_or_update_visitor(name=clean_name, email=clean_email)
        token = auth_service.issue_visitor_token(
            visitor_id=result["visitor_id"],
            name=result["name"],
            email=result["email"],
        )
        result["access_token"] = token
        return VisitorRegisterResponse(**result)
    except VisitorServiceError as exc:
        logger.warning("visitor_registration_error ip=%s err=%s", client_ip, exc)
        # Return a generic message — do not leak Supabase internals
        raise AppError(
            503,
            "registration_unavailable",
            "Registration service is temporarily unavailable. Please try again.",
        ) from exc

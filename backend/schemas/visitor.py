"""Pydantic schemas for AwanAI visitor registration."""

from __future__ import annotations

from pydantic import EmailStr, Field

from .common import APIModel


class VisitorRegisterRequest(APIModel):
    """
    Request body for POST /api/v1/visitors/register.

    SECURITY NOTE: name and email are self-reported and NOT verified.
    Do not use these fields for access control or identity proof.
    """

    name: str = Field(min_length=2, max_length=255, description="Self-reported display name")
    email: EmailStr = Field(description="Self-reported email address (NOT verified)")


class VisitorRegisterResponse(APIModel):
    """Response returned after visitor registration or returning-visitor update."""

    visitor_id: str = Field(description="Supabase UUID for this visitor record")
    name: str
    email: str
    registered_at: str = Field(description="ISO 8601 timestamp of first registration")
    is_returning: bool = Field(description="True if this email was already in the visitors table")
    access_token: str | None = Field(default=None, description="Signed temporary session JWT")

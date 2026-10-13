"""
AwanAI Visitor Service — Supabase integration for unverified visitor registration.

SECURITY MODEL
--------------
* This service runs on the backend and uses the Supabase SERVICE ROLE key.
* The service-role key is NEVER sent to the frontend.
* The email is NOT verified. Do not use it for authentication or identity proof.
* RLS is enabled on the visitors table (see SQL migration).
  - The service-role bypasses RLS for inserts/upserts (required for this flow).
  - The anon key has NO read/write access to the visitors table.
* Rate limiting is enforced at the route level (see visitors.py router).
* Only a minimal, non-sensitive subset of visitor data is returned to the frontend.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Fallback store for local testing / offline dev environments when Supabase is paused
_dev_local_visitors: dict[str, dict] = {}


class VisitorServiceError(Exception):
    """Raised when visitor registration fails."""


def _get_supabase_client():
    """Lazily import and construct the Supabase admin client using the service-role key."""
    try:
        from supabase import create_client  # type: ignore
    except ImportError as exc:
        raise VisitorServiceError(
            "supabase-py is not installed. Run: pip install supabase"
        ) from exc

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise VisitorServiceError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the environment."
        )

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _dev_fallback_register(name: str, email: str) -> dict:
    """Local fallback registration used only in development when Supabase is unreachable."""
    now = datetime.now(timezone.utc).isoformat()
    clean_email = email.lower()
    if clean_email in _dev_local_visitors:
        rec = _dev_local_visitors[clean_email]
        rec["name"] = name
        rec["last_seen_at"] = now
        logger.info("dev_fallback_visitor_returning id=%s", rec["id"])
        return {
            "visitor_id": rec["id"],
            "name": name,
            "email": clean_email,
            "registered_at": rec["created_at"],
            "is_returning": True,
        }
    vid = str(uuid.uuid4())
    rec = {
        "id": vid,
        "name": name,
        "email": clean_email,
        "created_at": now,
        "last_seen_at": now,
    }
    _dev_local_visitors[clean_email] = rec
    logger.info("dev_fallback_visitor_registered id=%s", vid)
    return {
        "visitor_id": vid,
        "name": name,
        "email": clean_email,
        "registered_at": now,
        "is_returning": False,
    }


def register_or_update_visitor(name: str, email: str) -> dict:
    """
    Upsert a visitor record in the Supabase `visitors` table.

    Behaviour:
    - If the email is new: insert a new record and return is_returning=False.
    - If the email exists: update name and last_seen_at, return is_returning=True.

    Returns a dict with visitor_id, name, email, registered_at, is_returning.

    Raises VisitorServiceError on any database failure in production.
    In development, falls back to local storage if Supabase is offline/paused.

    IMPORTANT: email is self-reported and unverified. This function must not be
    used to infer identity or grant any access based on the email alone.
    """
    now = datetime.now(timezone.utc).isoformat()

    try:
        client = _get_supabase_client()
        # Check if visitor already exists
        existing = (
            client.table("visitors")
            .select("id,name,email,created_at")
            .eq("email", email.lower())
            .limit(1)
            .execute()
        )
        data = existing.data if existing.data else []

        if data:
            # Returning visitor — update name and last_seen_at
            visitor_id = data[0]["id"]
            client.table("visitors").update(
                {"name": name, "last_seen_at": now}
            ).eq("id", visitor_id).execute()

            logger.info("visitor_returning id=%s", visitor_id)
            return {
                "visitor_id": visitor_id,
                "name": name,
                "email": email.lower(),
                "registered_at": data[0]["created_at"],
                "is_returning": True,
            }
        else:
            # New visitor — insert
            insert_result = (
                client.table("visitors")
                .insert(
                    {
                        "name": name,
                        "email": email.lower(),
                        "created_at": now,
                        "last_seen_at": now,
                    }
                )
                .execute()
            )
            inserted = insert_result.data[0] if insert_result.data else {}
            visitor_id = inserted.get("id", str(uuid.uuid4()))

            logger.info("visitor_registered id=%s", visitor_id)
            return {
                "visitor_id": visitor_id,
                "name": name,
                "email": email.lower(),
                "registered_at": now,
                "is_returning": False,
            }

    except Exception as exc:
        if settings.app_env != "production":
            logger.warning(
                "Supabase unreachable (%s). Using development fallback for visitor registration.",
                exc,
            )
            return _dev_fallback_register(name, email)
        logger.error("visitor_registration_failed error=%s", exc)
        raise VisitorServiceError("Visitor registration could not be completed.") from exc

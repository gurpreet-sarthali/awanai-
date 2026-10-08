"""API routes for user feedback and AI response ratings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_current_user, get_monitoring_service
from backend.core.user_model import UserRecord
from backend.schemas.monitoring import AIMessageFeedbackCreate, UserFeedbackCreate
from backend.services.monitoring_service import MonitoringService

router = APIRouter(tags=["feedback"])


@router.post("/api/v1/feedback", status_code=201)
def submit_general_feedback(
    payload: UserFeedbackCreate,
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Submit platform user feedback (rating, comment, feedback_type)."""
    return monitoring_service.submit_general_feedback(
        user_id=current_user.id,
        feedback_type=payload.feedback_type,
        rating=payload.rating,
        comment=payload.comment,
    )


@router.get("/api/v1/feedback/me")
def get_my_feedback(
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> list[dict[str, Any]]:
    """List feedback submitted by the authenticated user."""
    all_feedback = monitoring_service.repository.get_recent_feedback(limit=100)
    return [fb for fb in all_feedback if fb["user_id"] == current_user.id]


@router.post("/api/v1/messages/{message_id}/feedback", status_code=201)
def submit_ai_message_feedback(
    message_id: str,
    payload: AIMessageFeedbackCreate,
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Rate an AI response message (helpful / not_helpful) with optional reason."""
    return monitoring_service.submit_message_feedback(
        message_id=message_id,
        user_id=current_user.id,
        rating=payload.rating,
        reason=payload.reason,
        comment=payload.comment,
    )

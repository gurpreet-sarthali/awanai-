"""Pydantic schemas for user feedback and monitoring."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class UserFeedbackCreate(BaseModel):
    feedback_type: Literal["bug", "incorrect_answer", "feature_request", "usability", "general"] = "general"
    rating: int = Field(default=5, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class AIMessageFeedbackCreate(BaseModel):
    rating: Literal["helpful", "not_helpful"]
    reason: Literal["incorrect_result", "poor_explanation", "wrong_chart", "question_misunderstood", "other"] | None = None
    comment: str | None = Field(default=None, max_length=1000)


class AdminCleanupRequest(BaseModel):
    usage_retention_days: int = Field(default=90, ge=1, le=365)
    error_retention_days: int = Field(default=30, ge=1, le=365)

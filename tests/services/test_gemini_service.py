import json

import pytest

from backend.schemas.ai import AnalyticsPlan
from backend.services.gemini_service import AIConfigurationError, AIServiceError, GeminiService, UnsupportedQuestionError
from backend.services.rate_limiter import AIRateLimitError, AIRateLimiter


class FakeResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload)


class FakeModels:
    def __init__(self, payload):
        self.payload = payload

    def generate_content(self, **kwargs):
        return FakeResponse(self.payload)


class FakeClient:
    def __init__(self, payload):
        self.models = FakeModels(payload)


SCHEMA = {"table": "placement", "columns": ["CGPA", "Placement"], "types": {}, "allowed_values": {}}


def test_valid_plan_is_parsed_and_validated():
    service = GeminiService(FakeClient({"intent": "comparison", "operation": "placement_by_internship", "filters": [], "chart_type": "bar", "needs_chart": True}))
    plan = service.plan("Compare internships", SCHEMA)
    assert isinstance(plan, AnalyticsPlan)
    assert plan.operation == "placement_by_internship"


def test_unsupported_operation_is_rejected():
    service = GeminiService(FakeClient({"intent": "lookup", "operation": "arbitrary_sql", "filters": [], "needs_chart": False}))
    with pytest.raises(UnsupportedQuestionError):
        service.plan("Do something", SCHEMA)


def test_unknown_filter_column_is_rejected():
    service = GeminiService(FakeClient({"intent": "comparison", "operation": "placement_by_internship", "filters": [{"field": "Branch", "value": "CSE"}], "needs_chart": False}))
    with pytest.raises(UnsupportedQuestionError):
        service.plan("Only CSE", SCHEMA)


def test_missing_key_fails_before_client_creation(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    service = GeminiService()
    with pytest.raises(AIConfigurationError):
        _ = service.client


def test_malformed_gemini_payload_is_rejected():
    service = GeminiService(FakeClient({"unexpected": True}))
    with pytest.raises(AIServiceError):
        service.plan("Compare internships", SCHEMA)


def test_rate_limiter_blocks_after_configured_limit():
    limiter = AIRateLimiter(per_minute=1, per_day=1)
    limiter.check()
    with pytest.raises(AIRateLimitError):
        limiter.check()
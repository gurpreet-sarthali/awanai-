import pandas as pd

from backend.schemas.ai import AnalyticsPlan, ExplanationPayload
from backend.services.ai_orchestration_service import AIOrchestrationService
from backend.services.rate_limiter import AIRateLimiter
from tests.api.test_api import FakeRepository, dataframe


class FakeGemini:
    def plan(self, question, schema_context):
        return AnalyticsPlan(intent="comparison", operation="placement_by_internship", filters=[], chart_type="bar", needs_chart=True)

    def explain(self, question, operation, result, warnings):
        return ExplanationPayload(answer="The observed rates are available by internship group.", insights=["The groups differ in this dataset."], recommendations=["Review the pattern with other factors."], warnings=[])


class FakeVisualization:
    def generate(self, chart_type, operation, **kwargs):
        return {"success": True, "chart_type": "bar", "title": "Placement Rate", "file_path": "C:/private/chart.png"}


def test_orchestration_executes_real_analytics_service_and_explains_result():
    repository = FakeRepository()
    analytics = __import__("backend.services.analytics_service", fromlist=["AnalyticsService"]).AnalyticsService(repository)
    service = AIOrchestrationService(repository, analytics, FakeVisualization(), FakeGemini(), AIRateLimiter(10, 10))
    result = service.analyze("Compare placement by internship")
    assert result.metrics
    assert result.analysis["operation"] == "placement_by_internship"
    assert result.warnings
    assert result.chart["file_path"] == "C:/private/chart.png"
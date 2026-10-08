from fastapi.testclient import TestClient

from backend.api.dependencies import get_ai_service
from backend.main import app
from backend.schemas.ai import AIAnalysisResponse, AIPlanResponse, AnalyticsPlan


class FakeAIService:
    def plan(self, question: str, dataset_id: str = "demo-placement") -> AIPlanResponse:
        return AIPlanResponse(question=question, plan=AnalyticsPlan(intent="comparison", operation="placement_by_internship", filters=[], chart_type="bar", needs_chart=True))

    def analyze(self, question: str, dataset_id: str = "demo-placement") -> AIAnalysisResponse:
        return AIAnalysisResponse(question=question, answer="Observed rates are available by internship.", metrics=[{"group": "Yes", "value": 16.3}], chart={"file_path": "C:/private/chart.png", "title": "Placement", "chart_type": "bar"}, insights=["The groups differ."], recommendations=["Review other factors."], warnings=["Association does not establish causation."], analysis={"operation": "placement_by_internship", "filters": [], "chart_type": "bar", "needs_chart": True})


def test_ai_plan_and_analyze_endpoints_hide_filesystem_path():
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    client = TestClient(app)
    plan = client.post("/api/v1/ai/plan", json={"question": "Compare internships"})
    analysis = client.post("/api/v1/ai/analyze", json={"question": "Compare internships"})
    app.dependency_overrides.clear()
    assert plan.status_code == 200
    assert plan.json()["plan"]["operation"] == "placement_by_internship"
    assert analysis.status_code == 200
    body = analysis.json()
    assert body["chart"]["file_url"].endswith("/chart.png")
    assert "C:/private" not in analysis.text
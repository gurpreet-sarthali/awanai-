import pandas as pd
from fastapi.testclient import TestClient

from backend.api.dependencies import get_analytics_service, get_dataset_service, get_repository, get_visualization_service
from backend.main import app
from backend.repositories.database_repository import DatabaseRepository
from backend.services.analytics_service import AnalyticsService
from backend.services.dataset_service import DatasetService
from backend.services.visualization_service import VisualizationService


def dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "College_ID": ["A", "B", "C", "D"],
            "IQ": [100, 110, 90, 105],
            "Prev_Sem_Result": [8.0, 7.0, 6.0, 8.5],
            "CGPA": [8.0, 7.0, 6.0, 8.5],
            "Academic_Performance": [8, 6, 4, 9],
            "Internship_Experience": ["Yes", "No", "No", "Yes"],
            "Extra_Curricular_Score": [8, 6, 3, 9],
            "Communication_Skills": [8, 6, 3, 9],
            "Projects_Completed": [2, 1, 0, 5],
            "Placement": ["Yes", "No", "No", "Yes"],
        }
    )


class FakeRepository(DatabaseRepository):
    def __init__(self) -> None:
        pass

    def check_connection(self) -> bool:
        return True

    def resolve_table(self, dataset_id: str) -> tuple[str, list[str]]:
        return "placement", list(dataframe().columns)

    def load_dataframe(self, dataset_id: str = "demo-placement") -> pd.DataFrame:
        return dataframe()

    def schema(self, dataset_id: str = "demo-placement") -> list[dict[str, object]]:
        return [{"name": "College_ID", "data_type": "varchar(20)", "nullable": False, "primary_key": False}]

    def sample(self, dataset_id: str, limit: int) -> list[dict[str, object]]:
        return dataframe().head(limit).to_dict(orient="records")


def client(tmp_path):
    repository = FakeRepository()
    analytics = AnalyticsService(repository)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_dataset_service] = lambda: DatasetService(repository)
    app.dependency_overrides[get_analytics_service] = lambda: analytics
    app.dependency_overrides[get_visualization_service] = lambda: VisualizationService(analytics, tmp_path)
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_health_and_database_health(tmp_path):
    api = client(tmp_path)
    assert api.get("/api/v1/health").status_code == 200
    assert api.get("/api/v1/health/database").json()["database"] == "reachable"


def test_dataset_endpoints(tmp_path):
    api = client(tmp_path)
    summary = api.get("/api/v1/dataset/summary")
    assert summary.status_code == 200
    assert summary.json()["rows"] == 4
    assert api.get("/api/v1/dataset/schema").status_code == 200
    assert len(api.get("/api/v1/dataset/sample?limit=2").json()["rows"]) == 2


def test_analytics_endpoints_and_allowlist(tmp_path):
    api = client(tmp_path)
    assert api.get("/api/v1/analytics/summary").status_code == 200
    assert api.get("/api/v1/analytics/placement").status_code == 200
    assert api.get("/api/v1/analytics/internship").status_code == 200
    assert api.get("/api/v1/analytics/cgpa").status_code == 200
    assert api.get("/api/v1/analytics/projects").status_code == 200
    assert api.post("/api/v1/analytics/run", json={"operation": "overall_placement_rate"}).status_code == 200
    invalid = api.post("/api/v1/analytics/run", json={"operation": "arbitrary_sql"})
    assert invalid.status_code == 400
    assert invalid.json()["error"] == "invalid_operation"


def test_visualization_endpoint_and_invalid_chart(tmp_path):
    api = client(tmp_path)
    response = api.post("/api/v1/visualizations/generate", json={"chart_type": "bar", "analysis_operation": "placement_by_internship"})
    assert response.status_code == 200
    assert response.json()["file_url"].startswith("/api/v1/visualizations/files/")
    invalid = api.post("/api/v1/visualizations/generate", json={"chart_type": "radar", "analysis_operation": "placement_by_internship"})
    assert invalid.status_code == 400


def test_invalid_request_body(tmp_path):
    api = client(tmp_path)
    response = api.post("/api/v1/analytics/run", json={})
    assert response.status_code == 422
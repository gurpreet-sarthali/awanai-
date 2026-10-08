import pandas as pd
from fastapi.testclient import TestClient

from backend.api.dependencies import get_query_manager
from backend.main import app
from backend.ai.nlsql.query_manager import QueryManager
from tests.api.test_api import FakeRepository


class NLSQLFakeRepository(FakeRepository):
    def schema(self, dataset_id: str = "demo-placement"):
        return [
            {"name": column, "data_type": "varchar" if column in {"College_ID", "Placement", "Internship_Experience"} else "decimal", "nullable": True, "primary_key": False}
            for column in self.load_dataframe(dataset_id).columns
        ]


def test_nlsql_validate_endpoint_uses_mock_provider():
    app.dependency_overrides[get_query_manager] = lambda: QueryManager(NLSQLFakeRepository())
    client = TestClient(app)
    response = client.post("/api/v1/nlsql/validate", json={"question": "What is the average CGPA of placed students?"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["plan"]["metric_column"] == "CGPA"
    assert "%s" in response.json()["sql"]
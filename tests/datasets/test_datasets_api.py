from fastapi.testclient import TestClient

from backend.api.dependencies import get_dataset_management_service, get_repository
from backend.main import app
from backend.repositories.database_repository import DatabaseRepository
from backend.services.dataset_management_service import DatasetManagementService
from tests.test_helpers import RegistryStub, access_service, make_user


class RepoStub(DatabaseRepository):
    def __init__(self) -> None:
        pass

    def resolve_table(self, dataset_id: str):
        return "placement", ["region", "sales"]

    def sample(self, dataset_id: str, limit: int):
        return [{"region": "North", "sales": 100}]


def management_service(tmp_path):
    registry = RegistryStub()

    class ImportStub:
        def drop_table_if_exists(self, table_name):
            return None

    return DatasetManagementService(registry, ImportStub(), tmp_path, access_service(registry))


def client(tmp_path):
    service = management_service(tmp_path)
    repo = RepoStub()
    app.dependency_overrides[get_dataset_management_service] = lambda: service
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_list_and_get_dataset(tmp_path):
    api = client(tmp_path)
    listed = api.get("/api/v1/datasets")
    assert listed.status_code == 200
    body = listed.json()
    assert any(item["dataset_id"] == "demo-placement" for item in body["datasets"])
    detail = api.get("/api/v1/datasets/demo-placement")
    assert detail.status_code == 200
    assert detail.json()["dataset_name"] == "Demo Placement Dataset"


def test_preview_and_invalid_dataset(tmp_path):
    api = client(tmp_path)
    preview = api.get("/api/v1/datasets/demo-placement/preview?limit=1")
    assert preview.status_code == 200
    assert len(preview.json()["rows"]) == 1
    missing = api.get("/api/v1/datasets/not-a-valid-id/preview")
    assert missing.status_code == 404

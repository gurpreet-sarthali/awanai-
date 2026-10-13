"""
Unit and integration tests for AwanAI visitor onboarding and temporary CSV storage.
"""

import io
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.auth_service import AuthService
from backend.api.dependencies import get_auth_service, get_current_user, get_dataset_management_service
import pytest

client = TestClient(app)
pytestmark = pytest.mark.no_auth_mock


def test_visitor_registration_flow():
    # 1. Valid visitor registration
    payload = {"name": "Awan Explorer", "email": "explorer@example.com"}
    res = client.post("/api/v1/visitors/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Awan Explorer"
    assert data["email"] == "explorer@example.com"
    assert data["visitor_id"]
    assert data["is_returning"] is False
    assert data["access_token"]

    # 2. Returning visitor
    res2 = client.post("/api/v1/visitors/register", json={"name": "Awan Explorer Updated", "email": "explorer@example.com"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_returning"] is True
    assert data2["name"] == "Awan Explorer Updated"
    assert data2["access_token"]


def test_visitor_validation_errors():
    # Short name (< 2 chars) -> 400 or 422
    res = client.post("/api/v1/visitors/register", json={"name": "A", "email": "a@example.com"})
    assert res.status_code in (400, 422)

    # Invalid email format -> 422
    res2 = client.post("/api/v1/visitors/register", json={"name": "Valid Name", "email": "not-an-email"})
    assert res2.status_code in (400, 422)


def test_visitor_session_token_and_dataset_isolation():
    import traceback
    try:
        # Register visitor A
        res_a = client.post("/api/v1/visitors/register", json={"name": "Visitor A", "email": "a_iso@test.com"})
        assert res_a.status_code == 200, f"Register A failed: {res_a.text}"
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Register visitor B
        res_b = client.post("/api/v1/visitors/register", json={"name": "Visitor B", "email": "b_iso@test.com"})
        assert res_b.status_code == 200, f"Register B failed: {res_b.text}"
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Visitor A uploads a temporary CSV
        csv_content = b"student_id,score,status\n1,95,pass\n2,88,pass\n3,42,fail\n"
        files = {"file": ("test_scores.csv", io.BytesIO(csv_content), "text/csv")}
        upload_res = client.post("/api/v1/datasets/upload", headers=headers_a, files=files, data={"dataset_name": "Visitor A Scores"})
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.status_code} {upload_res.text}"
        ds_data = upload_res.json()
        dataset_id = ds_data["dataset_id"]

        # Visitor A can list their uploaded dataset
        list_a = client.get("/api/v1/datasets", headers=headers_a)
        assert list_a.status_code == 200, f"List A failed: {list_a.text}"
        a_ids = [d["dataset_id"] for d in list_a.json()["datasets"]]
        assert dataset_id in a_ids

        # Visitor B CANNOT see Visitor A's uploaded dataset
        list_b = client.get("/api/v1/datasets", headers=headers_b)
        assert list_b.status_code == 200, f"List B failed: {list_b.text}"
        b_ids = [d["dataset_id"] for d in list_b.json()["datasets"]]
        assert dataset_id not in b_ids

        # Visitor B CANNOT delete Visitor A's dataset
        del_b = client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers_b)
        assert del_b.status_code in (400, 403, 404), f"Del B unexpected status: {del_b.status_code} {del_b.text}"

        # Visitor A CAN delete their dataset
        del_a = client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers_a)
        assert del_a.status_code == 200, f"Del A failed: {del_a.status_code} {del_a.text}"
    except Exception as exc:
        with open("test_fail.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise


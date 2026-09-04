from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_unknown_job_returns_404_with_error_code():
    with TestClient(app) as client:
        response = client.get("/reconciliation/jobs/job_does_not_exist")
        assert response.status_code == 404
        assert response.json()["code"] == "JOB_NOT_FOUND"

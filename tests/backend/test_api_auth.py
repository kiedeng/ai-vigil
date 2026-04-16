from fastapi.testclient import TestClient

from backend.app.main import app


def test_login_rejects_bad_password():
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})

    assert response.status_code == 401


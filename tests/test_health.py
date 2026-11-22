from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_the_configured_dev_origin_only():
    allowed = client.options("/api/v1/compliance/evaluate", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    blocked = client.options("/api/v1/compliance/evaluate", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in blocked.headers

"""T025 - GET /v1/health conforms to contracts/openapi.yaml (Health schema), AC1.1."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _assert_health_shape(body: dict) -> None:
    assert set(body) >= {"status", "checks"}
    assert body["status"] in {"ok", "degraded"}
    assert isinstance(body["checks"], dict)
    assert all(v in {"ok", "down"} for v in body["checks"].values())


def test_health_endpoint_requires_no_authentication_and_matches_schema() -> None:
    response = client.get("/v1/health")
    assert response.status_code in {200, 503}
    _assert_health_shape(response.json())


def test_health_reports_db_and_redis_checks() -> None:
    body = client.get("/v1/health").json()
    assert {"db", "redis"} <= set(body["checks"])


def test_health_status_is_consistent_with_http_code() -> None:
    response = client.get("/v1/health")
    body = response.json()
    healthy = all(v == "ok" for v in body["checks"].values())
    assert (response.status_code == 200) == healthy
    assert body["status"] == ("ok" if healthy else "degraded")

"""Shared fixtures for integration, contract and e2e tests (real PostgreSQL, no mocks).

Nothing here is autouse: unit tests never touch the database.
"""
import subprocess
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql

TABLES = "sync_conflicts, applied_ops, trial_records, parcels, farm_members, farms"


@pytest.fixture(scope="session")
def migrated() -> None:
    result = subprocess.run(
        ["alembic", "upgrade", "head"], capture_output=True, text=True, cwd="/app"
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def clean_db(migrated: None) -> None:
    sql(f"TRUNCATE {TABLES} CASCADE")


@pytest.fixture
def client(clean_db: None) -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def token_for(client: TestClient) -> Callable[[uuid.UUID], str]:
    def _token(user_id: uuid.UUID) -> str:
        r = client.post("/v1/auth/dev-token", json={"user_id": str(user_id)})
        assert r.status_code == 200, r.text
        return str(r.json()["token"])

    return _token


@pytest.fixture
def make_farm() -> Callable[[dict[uuid.UUID, str]], uuid.UUID]:
    """Create a farm with the given {user_id: role} members."""

    def _make(members: dict[uuid.UUID, str]) -> uuid.UUID:
        farm_id = uuid.uuid4()
        sql("INSERT INTO farms (id, name) VALUES ($1, $2)", farm_id, "Test farm")
        for user_id, role in members.items():
            sql(
                "INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1, $2, $3)",
                farm_id,
                user_id,
                role,
            )
        return farm_id

    return _make


@pytest.fixture
def upload(client: TestClient) -> Callable[[str, list[dict[str, Any]]], dict[str, Any]]:
    def _upload(token: str, ops: list[dict[str, Any]]) -> dict[str, Any]:
        r = client.post("/v1/sync/upload", json={"ops": ops}, headers=auth(token))
        assert r.status_code == 200, r.text
        return dict(r.json())

    return _upload

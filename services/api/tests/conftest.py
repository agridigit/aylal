"""Shared fixtures for integration, contract and e2e tests (real PostgreSQL, no mocks).

Nothing here is autouse: unit tests never touch the database.

Isolation: integration and contract tests run against a throw-away database created for the
session (aylal_test_<random>) and dropped at the end, so they never truncate the shared dev
database nor depend on migrations applied by another branch. E2E tests keep the stack database
(see tests/e2e/conftest.py) because they go through the running API.
"""
import asyncio
import os
import subprocess
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql

TABLES = (
    "sync_conflicts, applied_ops, trial_records, worker_parcels, invitations, parcels,"
    " farm_members, farms, refresh_tokens, consents, otp_challenges, users"
)
DEFAULT_DB_URL = "postgresql://aylal:aylal_dev@db:5432/aylal"


def pytest_configure(config: pytest.Config) -> None:
    """Point the app at a per-session database name before any app module is imported."""
    if "AYLAL_STACK_DATABASE_URL" in os.environ:
        return
    stack_url = os.environ.get("AYLAL_DATABASE_URL", DEFAULT_DB_URL)
    os.environ["AYLAL_STACK_DATABASE_URL"] = stack_url
    os.environ["AYLAL_DATABASE_URL"] = f"{stack_url.rsplit('/', 1)[0]}/aylal_test_{uuid.uuid4().hex[:10]}"


def _admin(statement: str) -> None:
    import asyncpg

    async def _run() -> None:
        conn = await asyncpg.connect(os.environ["AYLAL_STACK_DATABASE_URL"])
        try:
            await conn.execute(statement)
        finally:
            await conn.close()

    asyncio.run(_run())


def _test_db_name() -> str:
    return os.environ["AYLAL_DATABASE_URL"].rsplit("/", 1)[1]


_created: list[str] = []


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    for name in _created:
        _admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def migrated() -> None:
    name = _test_db_name()
    _admin(f'CREATE DATABASE "{name}"')
    _created.append(name)
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

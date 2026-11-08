"""Shared fixtures for integration, contract and e2e tests (real PostgreSQL, no mocks).

Nothing here is autouse: unit tests never touch the database.

Isolation: integration and contract tests run against a throw-away database created for the
session (aylal_test_<random>, one per pytest-xdist worker) and dropped at the end, so they never
truncate the shared dev database nor depend on migrations applied by another branch.
Speed: migrations run once into a template database (aylal_tpl_<hash of alembic/>); each session
clones it with CREATE DATABASE ... TEMPLATE instead of replaying Alembic. E2E tests keep the stack database
(see tests/e2e/conftest.py) because they go through the running API.
"""
import asyncio
import hashlib
import os
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql

# Redis isolation: each pytest-xdist worker gets its own Redis database (1..8), so a FLUSHDB or a rate-limit counter
# in one worker never resets another worker's counters (flaky 429 tests). Without xdist the shared DB 0 is kept.
_XDIST = os.environ.get("PYTEST_XDIST_WORKER", "")
if _XDIST.startswith("gw") and _XDIST[2:].isdigit():
    _base = os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0").rsplit("/", 1)[0]
    os.environ["AYLAL_REDIS_URL"] = f"{_base}/{1 + int(_XDIST[2:]) % 15}"

TABLES = (
    "sync_conflicts, applied_ops, trial_records, worker_parcels, invitations, parcels,"
    " farm_members, farms, refresh_tokens, consents, otp_challenges, users, phyto_products, catalog_versions"
)
DEFAULT_DB_URL = "postgresql://aylal:aylal_dev@db:5432/aylal"


def pytest_configure(config: pytest.Config) -> None:
    """Point the app at a per-process database name before any app module is imported.

    xdist workers inherit the controller's environment, so ownership is tracked by PID: each
    process (controller or worker) gets its own database.
    """
    if os.environ.get("AYLAL_TEST_DB_PID") == str(os.getpid()):
        return
    stack_url = os.environ.setdefault(
        "AYLAL_STACK_DATABASE_URL", os.environ.get("AYLAL_DATABASE_URL", DEFAULT_DB_URL)
    )
    os.environ["AYLAL_DATABASE_URL"] = f"{stack_url.rsplit('/', 1)[0]}/aylal_test_{uuid.uuid4().hex[:10]}"
    os.environ["AYLAL_TEST_DB_PID"] = str(os.getpid())


def _admin(statement: str) -> None:
    """Run a statement on the stack database, serialized with template builds and clones
    (pytest-xdist workers share the cluster)."""
    import asyncpg

    async def _run() -> None:
        conn = await asyncpg.connect(os.environ["AYLAL_STACK_DATABASE_URL"])
        try:
            await conn.execute("SELECT pg_advisory_lock(424242)")
            await conn.execute(statement)
        finally:
            await conn.close()  # also releases the lock

    asyncio.run(_run())


def _test_db_name() -> str:
    return os.environ["AYLAL_DATABASE_URL"].rsplit("/", 1)[1]


_created: list[str] = []


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    for name in _created:
        _admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _template_name() -> str:
    """Changes whenever a migration (or the Alembic env) changes."""
    digest = hashlib.sha256()
    for path in sorted(Path("/app/alembic").rglob("*.py")):
        digest.update(path.name.encode() + path.read_bytes())
    return f"aylal_tpl_{digest.hexdigest()[:12]}"


def _ensure_template(template: str) -> None:
    import asyncpg

    async def _run() -> None:
        conn = await asyncpg.connect(os.environ["AYLAL_STACK_DATABASE_URL"])
        try:
            await conn.execute("SELECT pg_advisory_lock(424242)")
            if await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", template):
                return
            building = f"{template}_build"
            await conn.execute(f'DROP DATABASE IF EXISTS "{building}" WITH (FORCE)')
            await conn.execute(f'CREATE DATABASE "{building}"')
            base = os.environ["AYLAL_STACK_DATABASE_URL"].rsplit("/", 1)[0]
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd="/app",
                env={**os.environ, "AYLAL_DATABASE_URL": f"{base}/{building}"},
            )
            if result.returncode != 0:
                await conn.execute(f'DROP DATABASE IF EXISTS "{building}" WITH (FORCE)')
                raise AssertionError(result.stdout + result.stderr)
            # publish atomically, then drop templates of older migration sets
            await conn.execute(f'ALTER DATABASE "{building}" RENAME TO "{template}"')
            stale = await conn.fetch(
                "SELECT datname FROM pg_database WHERE datname LIKE 'aylal\\_tpl\\_%' AND datname <> $1",
                template,
            )
            for row in stale:
                await conn.execute(f'DROP DATABASE IF EXISTS "{row["datname"]}" WITH (FORCE)')
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.fixture(scope="session")
def migrated() -> None:
    name = _test_db_name()
    template = _template_name()
    _ensure_template(template)
    _admin(f'CREATE DATABASE "{name}" TEMPLATE "{template}"')
    _created.append(name)


@pytest.fixture(autouse=True)
def _integration_database(request: pytest.FixtureRequest) -> None:
    """Integration tests that call sql() without a database fixture still find their throw-away DB
    (otherwise the result depends on which test ran first on a pytest-xdist worker)."""
    if "integration" in request.node.path.parts:
        request.getfixturevalue("migrated")


@pytest.fixture
def clean_db(migrated: None) -> None:
    sql(f"TRUNCATE {TABLES} CASCADE")
    # F3/F4 fixtures insert global fx_* crops that no TRUNCATE above reaches; real reference crops stay.
    sql("DELETE FROM crops WHERE slug LIKE 'fx\\_%'")


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

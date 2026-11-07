"""Pure helpers shared by DB-backed tests."""
import asyncio
import os
import uuid
from typing import Any

import asyncpg

DEFAULT_DB_URL = "postgresql://aylal:aylal_dev@db:5432/aylal"


def db_url() -> str:
    """Read at call time: tests/conftest.py switches it to the per-session test database."""
    return os.environ.get("AYLAL_DATABASE_URL", DEFAULT_DB_URL)


def sql(query: str, *args: Any) -> list[asyncpg.Record]:
    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(db_url())
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def op(
    farm_id: uuid.UUID,
    record_id: uuid.UUID,
    *,
    kind: str = "patch",
    fields: dict[str, Any] | None = None,
    base_version: int = 0,
    op_id: uuid.UUID | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "op_id": str(op_id or uuid.uuid4()),
        "table": "trial_records",
        "kind": kind,
        "record_id": str(record_id),
        "farm_id": str(farm_id),
        "base_version": base_version,
        "fields": fields or {},
        **extra,
    }


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def record_row(record_id: uuid.UUID) -> asyncpg.Record | None:
    rows = sql("SELECT * FROM trial_records WHERE id = $1", record_id)
    return rows[0] if rows else None

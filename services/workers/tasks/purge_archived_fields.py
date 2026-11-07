"""Daily purge of fields archived for more than 90 days (CL). Children follow through ON DELETE CASCADE."""
import datetime as dt
import os
from typing import Any, Protocol


class FieldRepo(Protocol):
    async def purge_archived_fields(self, now: dt.datetime) -> int: ...


class SqlFieldRepo:
    """asyncpg adapter of the port (one transaction per run)."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")

    async def purge_archived_fields(self, now: dt.datetime) -> int:
        import asyncpg

        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                ids = [
                    r[0]
                    for r in await conn.fetch(
                        "SELECT id FROM parcels WHERE archived_at IS NOT NULL AND purge_after IS NOT NULL AND purge_after <= $1", now
                    )
                ]
                if not ids:
                    return 0
                await conn.execute("UPDATE parcels SET merged_into_id = NULL WHERE merged_into_id = ANY($1)", ids)
                await conn.execute("DELETE FROM parcels WHERE id = ANY($1)", ids)
                return len(ids)
        finally:
            await conn.close()


async def purge_archived_fields(ctx: dict[str, Any], now: dt.datetime | None = None) -> int:
    repo: FieldRepo = ctx.get("repo") or SqlFieldRepo()
    return await repo.purge_archived_fields(now or dt.datetime.now(dt.UTC))

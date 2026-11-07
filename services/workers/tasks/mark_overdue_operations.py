"""Daily flag of reminders whose planned operation date has passed (R4-A4). SQL lives behind the repo port.

An operation status is never changed here: "overdue" is derived from the date, never stored.
"""
import datetime as dt
import os
from typing import Any, Protocol


class OverdueRepo(Protocol):
    async def mark_overdue(self, today: dt.date) -> int: ...


class SqlOverdueRepo:
    """asyncpg adapter of the port (one statement, one transaction, idempotent)."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")

    async def mark_overdue(self, today: dt.date) -> int:
        import asyncpg

        conn = await asyncpg.connect(self._dsn)
        try:
            result = await conn.execute(
                "UPDATE operation_reminders r SET state = 'fired' FROM operations o"
                " WHERE o.id = r.operation_id AND o.farm_id = r.farm_id AND o.status = 'planned'"
                " AND r.state = 'scheduled' AND r.fire_on <= $1::date",
                today,
            )
            return int(result.split()[-1])
        finally:
            await conn.close()


async def mark_overdue_operations(ctx: dict[str, Any], today: dt.date | None = None) -> int:
    repo: OverdueRepo = ctx.get("repo") or SqlOverdueRepo()
    return await repo.mark_overdue(today or dt.datetime.now(dt.UTC).date())

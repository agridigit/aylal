"""Hourly purge of pending accounts without consent (FR-012). SQL lives behind the repo port."""
import datetime as dt
import os
from typing import Any, Protocol

PENDING_TTL = dt.timedelta(hours=24)

_ELIGIBLE = """
    SELECT u.id FROM users u
    WHERE u.status = 'pending' AND u.created_at < $1 AND u.display_name IS NULL
      AND NOT EXISTS (SELECT 1 FROM consents c WHERE c.user_id = u.id AND c.withdrawn_at IS NULL)
      AND NOT EXISTS (SELECT 1 FROM farm_members m WHERE m.user_id = u.id)
      AND NOT EXISTS (SELECT 1 FROM farms f WHERE f.owner_id = u.id)
"""


class AccountRepo(Protocol):
    async def purge_pending_accounts(self, now: dt.datetime) -> int: ...


class SqlAccountRepo:
    """asyncpg adapter of the port (one transaction per run)."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")

    async def purge_pending_accounts(self, now: dt.datetime) -> int:
        import asyncpg

        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                cutoff = now - PENDING_TTL
                for table in ("refresh_tokens", "consents"):
                    await conn.execute(f"DELETE FROM {table} WHERE user_id IN ({_ELIGIBLE})", cutoff)
                status = await conn.execute(f"DELETE FROM users WHERE id IN ({_ELIGIBLE})", cutoff)
                return int(status.split()[-1])
        finally:
            await conn.close()


async def purge_pending(ctx: dict[str, Any], now: dt.datetime | None = None) -> int:
    repo: AccountRepo = ctx.get("repo") or SqlAccountRepo()
    return await repo.purge_pending_accounts(now or dt.datetime.now(dt.UTC))

"""Daily expiry of invitations past their 30-day validity (R6-A3). SQL lives behind the repo port."""
import datetime as dt
import os
from typing import Any, Protocol


class InvitationRepo(Protocol):
    async def expire_invitations(self, now: dt.datetime) -> int: ...


class SqlInvitationRepo:
    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")

    async def expire_invitations(self, now: dt.datetime) -> int:
        import asyncpg

        conn = await asyncpg.connect(self._dsn)
        try:
            status = await conn.execute(
                "UPDATE invitations SET status = 'expired' WHERE status = 'pending' AND expires_at <= $1", now
            )
            return int(status.split()[-1])
        finally:
            await conn.close()


async def expire_invitations(ctx: dict[str, Any], now: dt.datetime | None = None) -> int:
    repo: InvitationRepo = ctx.get("repo") or SqlInvitationRepo()
    return await repo.expire_invitations(now or dt.datetime.now(dt.UTC))

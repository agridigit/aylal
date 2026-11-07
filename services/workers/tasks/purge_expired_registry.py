"""Daily purge of registry entries past their retention date (retain_until). SQL lives behind the repo port.

The deletion goes through the SECURITY DEFINER function purge_expired_registry: the registry stays append-only
for everyone else (triggers registry_append_only).
"""
import datetime as dt
import os
from typing import Any, Protocol


class RegistryRepo(Protocol):
    async def purge_expired_registry(self, today: dt.date) -> int: ...


class SqlRegistryRepo:
    """asyncpg adapter of the port (one call, one transaction)."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")

    async def purge_expired_registry(self, today: dt.date) -> int:
        import asyncpg

        conn = await asyncpg.connect(self._dsn)
        try:
            return int(await conn.fetchval("SELECT purge_expired_registry($1::date)", today))
        finally:
            await conn.close()


async def purge_expired_registry(ctx: dict[str, Any], today: dt.date | None = None) -> int:
    repo: RegistryRepo = ctx.get("repo") or SqlRegistryRepo()
    return await repo.purge_expired_registry(today or dt.datetime.now(dt.UTC).date())

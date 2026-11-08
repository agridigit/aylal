"""Shared plumbing of the F4 worker tasks (not a task): the asyncpg adapter of the plan engine and the cache invalidation."""
import datetime as dt
import os
import uuid
from collections.abc import Mapping
from typing import Any

from access_sql import asyncpg_query
from clock import Clock, FixedClock, system_clock


class AsyncpgDb:
    """The two calls the engine needs, on an asyncpg connection (named `:binds` become `$n`)."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def fetch(self, sql: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        query, args = asyncpg_query(sql, params)
        return [dict(r) for r in await self.conn.fetch(query, *args)]

    async def execute(self, sql: str, params: Mapping[str, Any]) -> None:
        query, args = asyncpg_query(sql, params)
        await self.conn.execute(query, *args)


def clock_for(now: str | dt.datetime | None, clock: Clock | None = None) -> Clock:
    """The injected clock: an explicit instant (ISO string or datetime), a given clock, or the system clock."""
    if clock is not None:
        return clock
    if now is None:
        return system_clock()
    return FixedClock(dt.datetime.fromisoformat(now) if isinstance(now, str) else now)


async def bump_irrigation_version(farm_id: uuid.UUID) -> None:
    """Invalidate the cached advice views of the farm (same key as the API cache)."""
    import redis.asyncio as redis

    client: Any = redis.from_url(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
    try:
        await client.incr(f"irrver:{farm_id}")
    finally:
        await client.aclose()

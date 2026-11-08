"""Shared plumbing of the F3 worker tasks (not a task): database connection and cache invalidation."""
import os
import uuid
from typing import Any

STAFF_SCOPE_USER = uuid.UUID(int=0)  # staff scope never reads :uid


def dsn() -> str:
    return os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")


async def bump_data_version(farm_id: uuid.UUID) -> None:
    """Invalidate the cached dashboards of the farm (same key as the API cache)."""
    import redis.asyncio as redis

    client: Any = redis.from_url(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
    try:
        await client.incr(f"dashver:{farm_id}")
    finally:
        await client.aclose()


async def param(conn: Any, key: str, default: Any = None) -> Any:
    """A monitoring parameter (jsonb value) or `default` when the reference table does not carry it."""
    import json

    raw = await conn.fetchval("SELECT value FROM monitoring_params WHERE key = $1", key)
    return default if raw is None else json.loads(raw) if isinstance(raw, str) else raw


async def load_thresholds(conn: Any) -> list[dict[str, Any]]:
    """Reference thresholds with plain floats (numeric columns arrive as Decimal)."""
    from decimal import Decimal

    return [{k: float(v) if isinstance(v, Decimal) else v for k, v in r.items()} for r in map(dict, await conn.fetch("SELECT * FROM crop_weather_thresholds"))]

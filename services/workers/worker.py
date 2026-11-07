"""Arq worker: health task and settings."""
import os
from typing import Any
from urllib.parse import urlparse

from arq.connections import RedisSettings


async def health(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


def _redis_settings() -> RedisSettings:
    u = urlparse(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
    return RedisSettings(host=u.hostname or "redis", port=u.port or 6379)


class WorkerSettings:
    functions = [health]
    redis_settings = _redis_settings()
    health_check_interval = 5

"""Arq worker: health task and settings."""
import os
from typing import Any
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings

from tasks.purge_deleted_accounts import purge_pending
from tasks.send_otp import send_otp


async def health(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


def _redis_settings() -> RedisSettings:
    u = urlparse(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
    return RedisSettings(host=u.hostname or "redis", port=u.port or 6379)


class WorkerSettings:
    functions = [health, send_otp, purge_pending]
    cron_jobs = [cron(purge_pending, minute=0)]
    redis_settings = _redis_settings()
    health_check_interval = 5

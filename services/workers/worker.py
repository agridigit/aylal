"""Arq worker: health task and settings."""
import os
from typing import Any
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings

from tasks.build_tiles import build_tiles
from tasks.expire_invitations import expire_invitations
from tasks.mark_overdue_operations import mark_overdue_operations
from tasks.purge_archived_fields import purge_archived_fields
from tasks.purge_deleted_accounts import purge_deleted, purge_pending
from tasks.purge_expired_registry import purge_expired_registry
from tasks.send_otp import send_otp


async def health(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


def _redis_settings() -> RedisSettings:
    u = urlparse(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
    return RedisSettings(host=u.hostname or "redis", port=u.port or 6379)


class WorkerSettings:
    functions = [health, send_otp, purge_pending, purge_deleted, expire_invitations, build_tiles, purge_archived_fields,
                 purge_expired_registry, mark_overdue_operations]
    cron_jobs = [
        cron(purge_pending, minute=0),
        cron(purge_deleted, hour=3, minute=0),
        cron(expire_invitations, hour=3, minute=30),
        cron(purge_archived_fields, hour=4, minute=0),
        cron(purge_expired_registry, hour=4, minute=30),
        cron(mark_overdue_operations, hour=5, minute=0),
    ]
    redis_settings = _redis_settings()
    health_check_interval = 5

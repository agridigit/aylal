"""Arq worker: health task and settings."""
import os
from typing import Any
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings

from tasks.backfill_parcel_vigor import backfill_parcel_vigor
from tasks.build_registry_export import build_registry_export
from tasks.build_tiles import build_tiles
from tasks.drain_backfill_jobs import drain_backfill_jobs
from tasks.detect_zones import detect_zones
from tasks.evaluate_alerts import evaluate_alerts
from tasks.expire_invitations import expire_invitations
from tasks.import_crop_thresholds import import_crop_thresholds
from tasks.import_phyto_catalog import import_phyto_catalog
from tasks.ingest_imagery import ingest_imagery
from tasks.mark_overdue_operations import mark_overdue_operations
from tasks.purge_archived_fields import purge_archived_fields
from tasks.purge_deleted_accounts import purge_deleted, purge_pending
from tasks.purge_expired_registry import purge_expired_registry
from tasks.recompute_status import recompute_status
from tasks.refresh_weather import refresh_weather
from tasks.send_daily_summary import send_daily_summary
from tasks.send_otp import send_otp


async def health(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


def _redis_settings() -> RedisSettings:
    u = urlparse(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
    return RedisSettings(host=u.hostname or "redis", port=u.port or 6379)


class WorkerSettings:
    functions = [health, send_otp, purge_pending, purge_deleted, expire_invitations, build_tiles, purge_archived_fields,
                 purge_expired_registry, mark_overdue_operations, build_registry_export, import_phyto_catalog,
                 refresh_weather, evaluate_alerts, import_crop_thresholds, recompute_status, detect_zones, send_daily_summary, ingest_imagery, backfill_parcel_vigor,
                 drain_backfill_jobs]
    cron_jobs = [
        cron(purge_pending, minute=0),
        cron(purge_deleted, hour=3, minute=0),
        cron(expire_invitations, hour=3, minute=30),
        cron(purge_archived_fields, hour=4, minute=0),
        cron(purge_expired_registry, hour=4, minute=30),
        cron(mark_overdue_operations, hour=5, minute=0),
        cron(import_phyto_catalog, day=1, hour=2, minute=0),
        cron(refresh_weather, minute=10),
        cron(evaluate_alerts, hour={0, 3, 6, 9, 12, 15, 18, 21}, minute=20),
        cron(recompute_status, minute=40),
        cron(detect_zones, hour=6, minute=0),
        cron(send_daily_summary, minute=5),
        cron(drain_backfill_jobs, minute={3, 13, 23, 33, 43, 53}),
    ]
    redis_settings = _redis_settings()
    health_check_interval = 5

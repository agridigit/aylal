"""Hands registry export jobs to the worker (arq over the stack's Redis). The job id is the only payload.

AYLAL_ENQUEUE_JOBS=0 (set on the in-process test runner only) enqueues nothing: the integration suites share the
database with the stack's worker and create `queued` jobs on purpose; the worker task has its own tests.
"""
import logging
import os
import uuid

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

log = logging.getLogger(__name__)


async def enqueue_registry_export(job_id: uuid.UUID | str) -> None:
    settings = get_settings()
    if os.environ.get("AYLAL_ENQUEUE_JOBS", "1") == "0":
        return
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("build_registry_export", str(job_id), _job_id=f"registry-export-{job_id}")
    finally:
        await pool.aclose()

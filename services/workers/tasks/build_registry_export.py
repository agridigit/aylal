"""Builds the PDF / XLSX files of a registry export job and stores them under server-generated keys.

queued -> running -> done (keys, sha256, row_count) or failed (no keys, the farm's slot is freed). A job that is not
`queued` is left untouched (idempotent). The current view only (no reversed entry), the job's farm and period only.
"""
import asyncio
import datetime as dt
import json
import logging
import os
import uuid
from typing import Any

import asyncpg
from export_job import MAX_ROWS, content_sha256, entry_to_row, export_key, render_pdf, render_xlsx

from tasks.object_storage import get_storage

log = logging.getLogger(__name__)
_CONTENT_TYPES = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
_ROWS = (
    "SELECT a.performed_on, a.parcel_name, a.crop_name, a.product_name, a.active_ingredients, a.dose, a.dose_unit, a.area_ha,"
    " a.operator_name, a.warnings, a.is_free_product,"
    " EXISTS (SELECT 1 FROM registry_entries r WHERE r.farm_id = a.farm_id AND r.operation_id = a.operation_id"
    "  AND r.parcel_id = a.parcel_id AND r.entry_kind = 'reversal' AND r.recorded_at < a.recorded_at) AS corrected"
    " FROM registry_current a WHERE a.farm_id = $1 AND a.performed_on BETWEEN $2 AND $3"
    " AND ($4::uuid IS NULL OR a.parcel_id = $4::uuid) ORDER BY a.performed_on, a.parcel_name, a.recorded_at, a.id"
)


def _formats(fmt: str) -> tuple[str, ...]:
    return ("pdf", "xlsx") if fmt == "both" else (fmt,)


async def _fail(conn: asyncpg.Connection, job_id: uuid.UUID) -> None:
    await conn.execute("UPDATE export_jobs SET state = 'failed', file_keys = NULL WHERE id = $1", job_id)


async def build_registry_export(ctx: dict[str, Any], job_id: uuid.UUID | str) -> None:
    job_id = uuid.UUID(str(job_id))
    dsn = os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")
    conn = await asyncpg.connect(dsn)
    try:
        job = await conn.fetchrow("UPDATE export_jobs SET state = 'running' WHERE id = $1 AND state = 'queued' RETURNING *", job_id)
        if job is None:
            return
        try:
            if job["row_count"] > MAX_ROWS:
                raise ValueError("export_too_large")
            records = await conn.fetch(_ROWS, job["farm_id"], job["period_from"], job["period_to"],
                                       job["parcel_id"] if job["scope"] == "parcel" else None)
            if len(records) > MAX_ROWS:
                raise ValueError("export_too_large")
            farm_name = await conn.fetchval("SELECT name FROM farms WHERE id = $1", job["farm_id"])
            catalog = await conn.fetchval("SELECT max(source_date) FROM catalog_versions")
            lang = job["lang"]
            rows = [entry_to_row(dict(r), lang) for r in records]
            meta = {"farm_name": farm_name or "", "period_from": job["period_from"], "period_to": job["period_to"],
                    "generated_at": dt.datetime.now(dt.UTC), "catalog_version": catalog.isoformat() if catalog else "-"}
            storage = ctx.get("storage") or get_storage()
            keys: dict[str, str] = {}
            for fmt in _formats(job["format"]):
                render = render_pdf if fmt == "pdf" else render_xlsx
                data = await asyncio.to_thread(render, rows, lang=lang, meta=meta)
                key = export_key(job["farm_id"], job_id, fmt)
                await storage.put(key, data, _CONTENT_TYPES[fmt])
                keys[fmt] = key
            await conn.execute(
                "UPDATE export_jobs SET state = 'done', file_keys = $2::jsonb, sha256 = $3, row_count = $4 WHERE id = $1",
                job_id, json.dumps(keys), content_sha256(rows), len(rows))
        except Exception:
            log.exception("registry export %s failed", job_id)
            await _fail(conn, job_id)
    finally:
        await conn.close()

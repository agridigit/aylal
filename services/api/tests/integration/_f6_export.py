"""Helpers for the registry export tests: bulk registry rows, finished jobs with real objects in MinIO (Morocco-hosted stack)."""
import asyncio
import datetime as dt
import json
import uuid

from tests.helpers import sql

EXPORT = {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "both", "scope": "farm", "lang": "fr"}
ALL_YEAR = (dt.date(2026, 1, 1), dt.date(2026, 12, 31))


def bulk_registry(farm, operation, parcel, n, *, day=dt.date(2026, 6, 1), recorded_by=None):
    """n application rows in one statement (fixture only)."""
    sql("INSERT INTO registry_entries (id, farm_id, operation_id, parcel_id, entry_kind, performed_on, parcel_name, crop_name, area_ha,"
        " product_name, is_free_product, dose, dose_unit, allocated_quantity, operator_name, warnings, recorded_by, retain_until)"
        " SELECT gen_random_uuid(), $1, $2, $3, 'application', $4, 'P', 'Tomate', 1, 'Prod', false, 1, 'L/ha', 1, 'Op', '[]'::jsonb, $5, $4::date + 1825"
        " FROM generate_series(1, $6)", farm, operation, parcel, day, recorded_by or uuid.uuid4(), n)


def storage():
    from app.operations.storage import get_storage

    return get_storage()


def put(key, data, content_type="application/octet-stream"):
    asyncio.run(storage().put(key, data, content_type))


def exists(key) -> bool:
    return asyncio.run(storage().exists(key))


def add_job(farm, user, *, state="done", fmt="both", files=True, expires=None, created=None, keys=None):
    """A job row (fixture). With files=True the PDF/XLSX objects exist in the object store under server-style keys."""
    job = uuid.uuid4()
    formats = ("pdf", "xlsx") if fmt == "both" else (fmt,)
    file_keys = keys or {f: f"farms/{farm}/exports/{job}/registry.{f}" for f in formats}
    if files and state == "done":
        for f, k in file_keys.items():
            put(k, b"%PDF-1.7 test" if f == "pdf" else b"PK\x03\x04 test")
    sql("INSERT INTO export_jobs (id, farm_id, requested_by, scope, period_from, period_to, format, lang, state, file_keys, sha256, row_count,"
        " expires_at, created_at) VALUES ($1,$2,$3,'farm','2026-01-01','2026-12-31',$4,'fr',$5,$6::jsonb,$7,1,$8,$9)",
        job, farm, user, fmt, state, json.dumps(file_keys) if state == "done" else None, "a" * 64 if state == "done" else None,
        expires or dt.datetime.now(dt.UTC) + dt.timedelta(days=7), created or dt.datetime.now(dt.UTC))
    return job

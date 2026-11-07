"""T072/T073 - the worker task `build_registry_export` renders the registry of a job into PDF and XLSX stored in the object store.

Real PostgreSQL and MinIO (compose stack). Registry rows are append-only (legal retention): each run uses fresh farm ids and
leaves its rows in place, it never deletes a farm that carries registry rows.
"""
import asyncio
import datetime as dt
import io
import json
import re
import uuid

from tests.integration.test_sql_account_repo import run

from tasks.build_registry_export import build_registry_export

PERIOD = (dt.date(2026, 1, 1), dt.date(2026, 12, 31))
LABELS_FR_COUNT = 11


async def seed(conn, *, rows=3, lang="fr", fmt="both", scope="farm"):
    farm, other, op, parcel, job = (uuid.uuid4() for _ in range(5))
    for f in (farm, other):
        await conn.execute("INSERT INTO farms (id, name) VALUES ($1, $2)", f, "Ferme Atlas" if f == farm else "Autre")
    ops = {}
    for f in (farm, other):
        ops[f] = uuid.uuid4()
        await conn.execute("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) VALUES ($1,$2,'phyto','2026-03-01','validated',$3)", ops[f], f, uuid.uuid4())

    async def entry(f, day, *, kind="application", supersedes=None, name="Cuprex"):
        rid = uuid.uuid4()
        await conn.execute(
            "INSERT INTO registry_entries (id, farm_id, operation_id, parcel_id, entry_kind, supersedes_id, performed_on, parcel_name, crop_name,"
            " area_ha, product_name, active_ingredients, is_free_product, dose, dose_unit, allocated_quantity, operator_name, warnings,"
            " recorded_by, retain_until) VALUES ($1,$2,$3,$4,$5,$6,$7,'Oliviers du bas','Olivier',1.5,$8,$9::jsonb,false,2,'L/ha',3,'Karim',$10::jsonb,$11,$12)",
            rid, f, ops[f], parcel, kind, supersedes, day, name, json.dumps([{"name": "cuivre", "concentration": "50%"}]),
            json.dumps([{"code": "dose_above_max", "severity": "warning"}]), uuid.uuid4(), day + dt.timedelta(days=1825))
        return rid

    for i in range(rows):
        await entry(farm, dt.date(2026, 3, 1 + i))
    gone = await entry(farm, dt.date(2026, 4, 1), name="Annulé")
    await entry(farm, dt.date(2026, 4, 1), kind="reversal", supersedes=gone, name="Annulé")
    await entry(farm, dt.date(2025, 12, 31), name="Hors période")
    await entry(other, dt.date(2026, 3, 1), name="AutreFerme")
    await conn.execute(
        "INSERT INTO export_jobs (id, farm_id, requested_by, scope, parcel_id, period_from, period_to, format, lang, state, row_count)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'queued',$10)", job, farm, uuid.uuid4(), scope, parcel if scope == "parcel" else None, *PERIOD, fmt, lang, rows)
    return farm, job


def storage():
    from tasks.object_storage import get_storage

    return get_storage()


def test_given_a_queued_job_when_the_worker_runs_then_pdf_and_xlsx_exist_at_server_keys_with_the_same_current_rows():
    async def scenario(conn):
        farm, job = await seed(conn)
        await build_registry_export({}, job)
        row = await conn.fetchrow("SELECT state, file_keys, sha256, row_count FROM export_jobs WHERE id=$1", job)
        keys = json.loads(row["file_keys"])
        files = {fmt: await storage().get(key) for fmt, key in keys.items()}
        return farm, job, row, keys, files

    farm, job, row, keys, files = run(scenario)
    assert row["state"] == "done" and row["row_count"] == 3 and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
    assert set(keys) == {"pdf", "xlsx"}
    for key in keys.values():
        assert re.fullmatch(rf"farms/{farm}/exports/{job}/[A-Za-z0-9._-]+", key)
    assert files["pdf"].startswith(b"%PDF") and b"/FontFile2" in files["pdf"]
    from openpyxl import load_workbook
    from pypdf import PdfReader

    ws = load_workbook(io.BytesIO(files["xlsx"])).active
    rows = list(ws.iter_rows(values_only=True))
    assert len(rows[0]) == LABELS_FR_COUNT and len(rows) == 1 + 3                      # header + the 3 current treatments of the period
    names = {r[3] for r in rows[1:]}
    assert names == {"Cuprex"}                                                          # no reversed, out-of-period or other-farm line
    assert row["sha256"] in (ws.oddFooter.center.text or "")
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(files["pdf"])).pages)
    assert row["sha256"] in text.replace("\n", "") and "AutreFerme" not in text and "Hors période" not in text and "Annulé" not in text


def test_given_a_single_format_or_arabic_when_the_worker_runs_then_only_that_file_is_made_and_the_sheet_is_right_to_left():
    async def scenario(conn):
        farm, job = await seed(conn, fmt="xlsx", lang="ar")
        await build_registry_export({}, job)
        keys = json.loads(await conn.fetchval("SELECT file_keys FROM export_jobs WHERE id=$1", job))
        return keys, await storage().get(keys["xlsx"])

    keys, data = run(scenario)
    assert set(keys) == {"xlsx"}
    from openpyxl import load_workbook

    assert load_workbook(io.BytesIO(data)).active.sheet_view.rightToLeft is True


def test_given_a_storage_failure_when_the_worker_runs_then_the_job_is_failed_without_keys_and_the_farm_can_export_again():
    class Broken:
        async def put(self, *a, **k):
            raise OSError("minio down")

    async def scenario(conn):
        farm, job = await seed(conn)
        await build_registry_export({"storage": Broken()}, job)
        row = await conn.fetchrow("SELECT state, file_keys FROM export_jobs WHERE id=$1", job)
        await conn.execute(  # the partial unique index must now accept a new queued job for the farm
            "INSERT INTO export_jobs (id, farm_id, requested_by, scope, period_from, period_to, format, lang, state, row_count)"
            " VALUES ($1,$2,$3,'farm','2026-01-01','2026-12-31','pdf','fr','queued',0)", uuid.uuid4(), farm, uuid.uuid4())
        return row

    row = run(scenario)
    assert row["state"] == "failed" and row["file_keys"] is None


def test_given_a_finished_job_when_the_task_runs_again_then_nothing_is_rewritten():
    async def scenario(conn):
        farm, job = await seed(conn, fmt="pdf")
        await build_registry_export({}, job)
        first = await conn.fetchrow("SELECT file_keys, sha256 FROM export_jobs WHERE id=$1", job)

        class Forbidden:
            async def put(self, *a, **k):
                raise AssertionError("a finished job was rendered again")

        await build_registry_export({"storage": Forbidden()}, job)
        return first, await conn.fetchrow("SELECT state, file_keys, sha256 FROM export_jobs WHERE id=$1", job)

    first, second = run(scenario)
    assert second["state"] == "done" and (second["file_keys"], second["sha256"]) == (first["file_keys"], first["sha256"])


def test_given_a_job_over_the_row_cap_when_the_worker_runs_then_it_fails_before_rendering():
    class Forbidden:
        async def put(self, *a, **k):
            raise AssertionError("rendered despite the cap")

    async def scenario(conn):
        farm, job = await seed(conn)
        await conn.execute("UPDATE export_jobs SET row_count = 10001 WHERE id=$1", job)
        await build_registry_export({"storage": Forbidden()}, job)
        return await conn.fetchval("SELECT state FROM export_jobs WHERE id=$1", job)

    assert run(scenario) == "failed"


def test_given_the_worker_settings_then_the_export_task_is_registered():
    import worker

    assert build_registry_export in worker.WorkerSettings.functions
    assert asyncio.iscoroutinefunction(build_registry_export)

"""T072 - R6 on the running stack: the worker builds the PDF and the XLSX from the registry (10 000 rows in under 60 s);
files are fetched through the short signed URLs; Arabic exports are right-to-left."""
import io
import time
import uuid

import httpx

from tests.e2e._f6 import BASE, field_with_crop, owner_with_farm, unique_phone
from tests.helpers import sql
from tests.integration._f6_export import bulk_registry

PHONE = unique_phone()
BODY = {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "both", "scope": "farm", "lang": "fr"}


def _wait(c, h, farm, job, limit=60.0):
    start = time.monotonic()
    while time.monotonic() - start < limit:
        got = c.get(f"/farms/{farm}/registry/exports/{job}", headers=h)
        assert got.status_code == 200, got.text
        if got.json()["state"] in ("done", "failed"):
            return got.json(), time.monotonic() - start
        time.sleep(0.5)
    raise AssertionError("export not finished in time")


def test_given_ten_thousand_registry_rows_when_exporting_then_pdf_and_xlsx_are_built_by_the_worker_in_under_a_minute() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        parcel, _ = field_with_crop(c, h, farm, "A", -7.60)
        second, _ = field_with_crop(c, h, farm, "B", -7.55)
        op_a, op_b = uuid.uuid4(), uuid.uuid4()
        for oid, pid in ((op_a, parcel), (op_b, second)):
            sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) VALUES ($1,$2,'phyto','2026-06-01','validated',$3)", oid, uuid.UUID(farm), uuid.uuid4())
        bulk_registry(uuid.UUID(farm), op_a, uuid.UUID(parcel), 10_000)
        bulk_registry(uuid.UUID(farm), op_b, uuid.UUID(second), 2)

        too_many = c.post(f"/farms/{farm}/registry/exports", headers=h, json=BODY)
        assert too_many.status_code == 422  # 10 002 rows: refused before any work
        started = time.monotonic()
        job = c.post(f"/farms/{farm}/registry/exports", headers=h, json={**BODY, "scope": "parcel", "parcel_id": parcel})
        assert job.status_code == 202, job.text
        done, _ = _wait(c, h, farm, job.json()["id"])
        elapsed = time.monotonic() - started
        assert done["state"] == "done" and done["row_count"] == 10_000 and elapsed < 60, (done, elapsed)
        assert set(done["downloads"]) == {"pdf", "xlsx"} and "file_keys" not in str(done)
        pdf = httpx.get(done["downloads"]["pdf"], timeout=30)
        xlsx = httpx.get(done["downloads"]["xlsx"], timeout=30)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and xlsx.status_code == 200
        from openpyxl import load_workbook

        ws = load_workbook(io.BytesIO(xlsx.content), read_only=True).active
        assert sum(1 for _ in ws.iter_rows()) == 1 + 10_000
        assert done["sha256"] in (load_workbook(io.BytesIO(xlsx.content)).active.oddFooter.center.text or "")

        arabic = c.post(f"/farms/{farm}/registry/exports", headers=h, json={**BODY, "scope": "parcel", "parcel_id": second, "format": "xlsx", "lang": "ar"})
        assert arabic.status_code == 202, arabic.text
        ar, _ = _wait(c, h, farm, arabic.json()["id"])
        assert ar["state"] == "done" and set(ar["downloads"]) == {"xlsx"} and ar["row_count"] == 2
        sheet = load_workbook(io.BytesIO(httpx.get(ar["downloads"]["xlsx"], timeout=30).content)).active
        assert sheet.sheet_view.rightToLeft is True and sheet.max_row == 3


def test_given_an_export_of_another_farm_when_a_stranger_asks_for_it_then_404_through_the_proxy() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, unique_phone())
        stranger, other_farm = owner_with_farm(c, unique_phone())
        job = c.post(f"/farms/{farm}/registry/exports", headers=h, json=BODY)
        assert job.status_code == 202, job.text
        assert c.get(f"/farms/{farm}/registry/exports/{job.json()['id']}", headers=stranger).status_code == 404
        assert c.get(f"/farms/{other_farm}/registry/exports/{job.json()['id']}", headers=stranger).status_code == 404

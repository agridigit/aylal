"""T048 - the worker task `import_phyto_catalog` imports the homologation catalogue hosted in Morocco (no external URL by default).

Source file: gzip-compressed JSON {"source_date", "products": [{name, registration_no, holder, active_ingredients,
homologation_expires_on, uses: [{crop_slug, max_dose, dose_unit, dar_days, max_applications}]}]} (<= 3 MB compressed).
The source is a port with `async fetch() -> bytes`; the default reads AYLAL_PHYTO_CATALOG_SOURCE (file:// or s3://), never http(s).
Real PostgreSQL (compose stack); the rows created here are deleted by the test (the catalogue is not registry data).
"""
import asyncio
import datetime as dt
import gzip
import hashlib
import json
import socket
import uuid

import pytest

from tests.integration.test_sql_account_repo import run

from tasks.import_phyto_catalog import import_phyto_catalog

MB = 1024 * 1024


class Source:
    def __init__(self, data: bytes):
        self.data, self.calls = data, 0

    async def fetch(self) -> bytes:
        self.calls += 1
        return self.data


def payload(tag, *, products=None, source_date="2026-10-01"):
    products = products if products is not None else [
        {"name": f"Cuprex {tag}", "registration_no": "R-1", "holder": "Holder", "homologation_expires_on": "2099-12-31",
         "active_ingredients": [{"name": "cuivre", "concentration": "50%"}],
         "uses": [{"crop_slug": "olive", "max_dose": 2.5, "dose_unit": "L/ha", "dar_days": 21, "max_applications": 3},
                  {"crop_slug": "tomato", "max_dose": 3, "dose_unit": "L/ha", "dar_days": None, "max_applications": None}]},
        {"name": f"Vieux {tag}", "homologation_expires_on": "2020-01-01", "active_ingredients": [{"name": "soufre", "concentration": "80%"}], "uses": []},
    ]
    return gzip.compress(json.dumps({"source_date": source_date, "products": products}).encode())


async def versions(conn, checksums):
    return await conn.fetch("SELECT * FROM catalog_versions WHERE checksum = ANY($1)", checksums)


async def cleanup(conn, checksums):
    ids = [r["id"] for r in await versions(conn, checksums)]
    await conn.execute("DELETE FROM phyto_products WHERE catalog_version_id = ANY($1)", ids)
    await conn.execute("DELETE FROM catalog_versions WHERE id = ANY($1)", ids)


def test_given_a_catalogue_file_when_importing_then_a_version_products_uses_and_expired_homologations_are_stored():
    tag = uuid.uuid4().hex[:8]
    data = payload(tag)
    digest = hashlib.sha256(data).hexdigest()

    async def scenario(conn):
        try:
            await import_phyto_catalog({"source": Source(data)})
            vs = await versions(conn, [digest])
            products = await conn.fetch("SELECT * FROM phyto_products WHERE catalog_version_id = $1 ORDER BY name", vs[0]["id"])
            uses = await conn.fetch("SELECT u.* FROM phyto_product_uses u JOIN phyto_products p ON p.id=u.product_id WHERE p.catalog_version_id=$1 ORDER BY crop_slug", vs[0]["id"])
            return vs, products, uses
        finally:
            await cleanup(conn, [digest])

    vs, products, uses = run(scenario)
    assert len(vs) == 1 and vs[0]["row_count"] == 2 and vs[0]["source_date"] == dt.date(2026, 10, 1) and vs[0]["checksum"] == digest
    live, old = products[0], products[1]
    assert live["name"] == f"Cuprex {tag}" and live["name_normalized"] == f"cuprex {tag}" and json.loads(live["active_ingredients"]) == [{"name": "cuivre", "concentration": "50%"}]
    assert live["expired_at"] is None and old["expired_at"] is not None and old["homologation_expires_on"] == dt.date(2020, 1, 1)
    assert [(u["crop_slug"], float(u["max_dose"]), u["dose_unit"], u["dar_days"], u["max_applications"]) for u in uses[:1]] == [("olive", 2.5, "L/ha", 21, 3)]
    assert uses[1]["crop_slug"] == "tomato" and uses[1]["dar_days"] is None


def test_given_the_same_file_imported_twice_when_importing_then_no_second_version_is_created():
    data = payload(uuid.uuid4().hex[:8])
    digest = hashlib.sha256(data).hexdigest()

    async def scenario(conn):
        try:
            await import_phyto_catalog({"source": Source(data)})
            await import_phyto_catalog({"source": Source(data)})
            return len(await versions(conn, [digest])), await conn.fetchval(
                "SELECT count(*) FROM phyto_products p JOIN catalog_versions v ON v.id=p.catalog_version_id WHERE v.checksum=$1", digest)
        finally:
            await cleanup(conn, [digest])

    assert run(scenario) == (1, 2)


def test_given_a_changed_file_when_importing_then_a_new_version_is_added_and_the_old_one_is_kept_for_past_snapshots():
    tag = uuid.uuid4().hex[:8]
    first, second = payload(tag), payload(tag, source_date="2026-11-01")
    digests = [hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest()]

    async def scenario(conn):
        try:
            await import_phyto_catalog({"source": Source(first)})
            await import_phyto_catalog({"source": Source(second)})
            vs = await versions(conn, digests)
            per = [await conn.fetchval("SELECT count(*) FROM phyto_products WHERE catalog_version_id=$1", v["id"]) for v in vs]
            return sorted(v["source_date"] for v in vs), per
        finally:
            await cleanup(conn, digests)

    dates, per = run(scenario)
    assert dates == [dt.date(2026, 10, 1), dt.date(2026, 11, 1)] and per == [2, 2]


@pytest.mark.parametrize("bad", [
    b"not gzip at all",
    gzip.compress(b"{not json"),
    gzip.compress(json.dumps({"source_date": "2026-10-01"}).encode()),
    gzip.compress(json.dumps({"source_date": "yesterday", "products": []}).encode()),
    gzip.compress(json.dumps({"source_date": "2026-10-01", "products": [{"name": "Ok"}, {"registration_no": "no name"}]}).encode()),
    gzip.compress(json.dumps({"source_date": "2026-10-01", "products": [{"name": "x" * 201, "uses": []}]}).encode()),
    gzip.compress(json.dumps({"source_date": "2026-10-01", "products": [{"name": "Ok", "uses": [{"crop_slug": "olive", "max_dose": -1}]}]}).encode()),
])
def test_given_an_invalid_file_when_importing_then_the_import_fails_and_nothing_at_all_is_written(bad):
    async def scenario(conn):
        before = (await conn.fetchval("SELECT count(*) FROM catalog_versions"), await conn.fetchval("SELECT count(*) FROM phyto_products"))
        with pytest.raises(ValueError):
            await import_phyto_catalog({"source": Source(bad)})
        return before, (await conn.fetchval("SELECT count(*) FROM catalog_versions"), await conn.fetchval("SELECT count(*) FROM phyto_products"))

    before, after = run(scenario)
    assert before == after


def test_given_a_file_over_three_megabytes_compressed_when_importing_then_it_is_refused_before_any_decompression():
    big = b"\x1f\x8b" + b"0" * (3 * MB + 1)  # would not even decompress: the size check must come first
    async def scenario(conn):
        before = await conn.fetchval("SELECT count(*) FROM catalog_versions")
        with pytest.raises(ValueError, match="catalog_too_large"):
            await import_phyto_catalog({"source": Source(big)})
        return before == await conn.fetchval("SELECT count(*) FROM catalog_versions")

    assert run(scenario)


def test_given_a_small_file_that_expands_enormously_when_importing_then_it_is_refused_without_parsing():
    bomb = gzip.compress(b" " * (80 * MB))
    assert len(bomb) < 3 * MB

    async def scenario(conn):
        before = await conn.fetchval("SELECT count(*) FROM catalog_versions")
        with pytest.raises(ValueError, match="catalog_too_large"):
            await import_phyto_catalog({"source": Source(bomb)})
        return before == await conn.fetchval("SELECT count(*) FROM catalog_versions")

    assert run(scenario)


def test_given_no_source_configured_when_importing_then_nothing_happens_and_no_connection_is_made(monkeypatch):
    monkeypatch.delenv("AYLAL_PHYTO_CATALOG_SOURCE", raising=False)

    def forbidden(*a, **k):
        raise AssertionError("a network connection was attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert asyncio.run(import_phyto_catalog({})) is None


@pytest.mark.parametrize("url", ["https://phyto.example.org/catalog.json.gz", "http://192.0.2.1/c.gz", "ftp://x/c.gz"])
def test_given_an_external_url_as_the_source_when_importing_then_it_is_rejected_without_any_connection(monkeypatch, url):
    monkeypatch.setenv("AYLAL_PHYTO_CATALOG_SOURCE", url)

    def forbidden(*a, **k):
        raise AssertionError("a network connection was attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    with pytest.raises(ValueError, match="catalog_source"):
        asyncio.run(import_phyto_catalog({}))


def test_given_a_local_file_source_when_importing_then_the_file_is_read_and_imported(tmp_path, monkeypatch):
    data = payload(uuid.uuid4().hex[:8])
    digest = hashlib.sha256(data).hexdigest()
    path = tmp_path / "catalog.json.gz"
    path.write_bytes(data)
    monkeypatch.setenv("AYLAL_PHYTO_CATALOG_SOURCE", f"file://{path}")

    async def scenario(conn):
        try:
            await import_phyto_catalog({})
            return len(await versions(conn, [digest]))
        finally:
            await cleanup(conn, [digest])

    assert run(scenario) == 1


def test_given_the_worker_settings_then_the_import_is_registered_and_scheduled_monthly():
    import worker

    assert import_phyto_catalog in worker.WorkerSettings.functions
    jobs = [c for c in worker.WorkerSettings.cron_jobs if c.coroutine is import_phyto_catalog]
    assert len(jobs) == 1 and jobs[0].day == 1

"""T071 - R6-A1 to R6-A5, SC-005: export request limits, one active job per farm under a lock, roles, farm isolation,
short signed URL limited to the farm and the requester, never a client-supplied key."""
import datetime as dt
import os
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql
from tests.integration._f6 import add_operation, add_registry, world  # noqa: F401
from tests.integration._f6_export import EXPORT, add_job, bulk_registry, put

D = dt.date


def request(client, token_for, who, farm, **kw):
    return client.post(f"/v1/farms/{farm}/registry/exports", headers=auth(token_for(who)), json={**EXPORT, **kw})


def status(client, token_for, who, farm, job):
    return client.get(f"/v1/farms/{farm}/registry/exports/{job}", headers=auth(token_for(who)))


def jobs(farm=None):
    return sql("SELECT count(*) FROM export_jobs" + (" WHERE farm_id=$1" if farm else ""), *([farm] if farm else []))[0][0]


def test_given_a_period_and_a_parcel_when_requesting_then_only_the_matching_treatments_are_counted(client, token_for, world):
    w = world
    op = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    op2 = add_operation(w["farm_a"], w["owner"], w["a2"], type_="phyto")
    add_registry(w["farm_a"], op, w["a1"], performed_on=D(2026, 3, 1))
    add_registry(w["farm_a"], op, w["a1"], performed_on=D(2026, 9, 1))
    add_registry(w["farm_a"], op, w["a1"], performed_on=D(2025, 12, 31))   # before the period
    add_registry(w["farm_a"], op2, w["a2"], performed_on=D(2026, 4, 1))
    parcel = request(client, token_for, w["owner"], w["farm_a"], scope="parcel", parcel_id=str(w["a1"]), period_to="2026-06-30")
    assert parcel.status_code == 202, parcel.text
    assert parcel.json()["row_count"] == 1 and parcel.json()["state"] == "queued"
    sql("UPDATE export_jobs SET state='done'")
    farm = request(client, token_for, w["owner"], w["farm_a"])
    assert farm.status_code == 202 and farm.json()["row_count"] == 3


def test_given_a_reversed_entry_when_requesting_then_only_the_current_view_is_counted(client, token_for, world):
    w = world
    op = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    first = add_registry(w["farm_a"], op, w["a1"], performed_on=D(2026, 3, 1))
    add_registry(w["farm_a"], op, w["a1"], performed_on=D(2026, 3, 1), kind="reversal", supersedes_id=first)
    add_registry(w["farm_a"], op, w["a1"], performed_on=D(2026, 3, 1))
    assert request(client, token_for, w["owner"], w["farm_a"]).json()["row_count"] == 1


def test_given_more_than_10000_rows_when_requesting_then_422_before_any_job_or_file_is_created(client, token_for, world):
    w = world
    op = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    bulk_registry(w["farm_a"], op, w["a1"], 10_001)
    before = jobs()
    r = request(client, token_for, w["owner"], w["farm_a"])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "export_too_large"
    assert jobs() == before


def test_given_exactly_10000_rows_when_requesting_then_the_export_is_queued(client, token_for, world):
    w = world
    op = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    bulk_registry(w["farm_a"], op, w["a1"], 10_000)
    r = request(client, token_for, w["owner"], w["farm_a"])
    assert r.status_code == 202 and r.json()["row_count"] == 10_000


def test_given_a_period_over_five_years_when_requesting_then_422_and_exactly_five_years_is_accepted(client, token_for, world):
    w = world
    over = request(client, token_for, w["owner"], w["farm_a"], period_from="2020-01-01", period_to="2025-01-02")
    assert over.status_code == 422
    assert request(client, token_for, w["owner"], w["farm_a"], period_from="2020-01-01", period_to="2025-01-01").status_code == 202
    sql("UPDATE export_jobs SET state='done'")
    assert request(client, token_for, w["owner"], w["farm_a"], period_from="2026-02-01", period_to="2026-01-01").status_code == 422


def test_given_an_active_job_when_requesting_another_then_409_and_a_finished_job_frees_the_slot(client, token_for, world):
    w = world
    assert request(client, token_for, w["owner"], w["farm_a"]).status_code == 202
    again = request(client, token_for, w["manager"], w["farm_a"])
    assert again.status_code == 409 and again.json()["detail"]["code"] == "export_already_active"
    assert request(client, token_for, w["owner_b"], w["farm_b"]).status_code == 202  # another farm is independent
    sql("UPDATE export_jobs SET state='done' WHERE farm_id=$1", w["farm_a"])
    assert request(client, token_for, w["owner"], w["farm_a"]).status_code == 202


def test_given_ten_exports_in_the_last_hour_when_requesting_an_eleventh_then_429(client, token_for, world):
    w = world
    for _ in range(10):
        add_job(w["farm_a"], w["owner"], files=False)
    r = request(client, token_for, w["owner"], w["farm_a"])
    assert r.status_code == 429 and r.headers["Retry-After"]


def test_given_two_simultaneous_requests_on_one_farm_when_racing_then_exactly_one_is_queued_and_the_other_gets_409_never_a_500(client, token_for, world):
    from app.main import app

    w = world
    token = token_for(w["owner"])

    def one(_):
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=auth(token), json=EXPORT).status_code

    for _ in range(3):
        sql("UPDATE export_jobs SET state='done'")
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = sorted(pool.map(one, range(2)))
        assert codes == [202, 409], codes
    assert sql("SELECT count(*) FROM export_jobs WHERE state IN ('queued','running')")[0][0] == 1


def test_given_a_worker_when_requesting_or_reading_an_export_then_403(client, token_for, world):
    w = world
    job = add_job(w["farm_a"], w["owner"], files=False, state="queued")
    assert request(client, token_for, w["worker"], w["farm_a"]).status_code == 403
    assert status(client, token_for, w["worker"], w["farm_a"], job).status_code == 403
    assert client.get(f"/v1/farms/{w['farm_a']}/registry", headers=auth(token_for(w["worker"]))).status_code == 403


def test_given_another_farm_or_an_outsider_when_requesting_or_reading_an_export_then_404_identical_to_an_unknown_job(client, token_for, world):
    w = world
    job = add_job(w["farm_a"], w["owner"], files=False, state="queued")
    ghost = status(client, token_for, w["owner"], w["farm_a"], uuid.uuid4())
    assert ghost.status_code == 404
    for who in ("owner_b", "outsider"):
        r = status(client, token_for, w[who], w["farm_a"], job)
        assert r.status_code == 404 and r.json() == ghost.json()
        assert request(client, token_for, w[who], w["farm_a"]).status_code == 404
    through_b = status(client, token_for, w["owner_b"], w["farm_b"], job)  # a job of farm A addressed through farm B
    assert through_b.status_code == 404 and through_b.json() == ghost.json()
    assert request(client, token_for, w["owner"], w["farm_a"], scope="parcel", parcel_id=str(w["b1"])).status_code == 404
    assert client.get(f"/v1/farms/{w['farm_a']}/registry/exports/{job}").status_code == 401


@pytest.mark.parametrize("extra", [{"file_keys": ["a"]}, {"key": "farms/x/exports/y/z.pdf"}, {"url": "https://evil.test/x"},
                                   {"download_url": "https://evil.test/x"}, {"bucket": "other"}])
def test_given_a_client_supplied_object_key_or_url_when_requesting_then_422_and_no_job_is_created(client, token_for, world, extra):
    w = world
    before = jobs()
    assert request(client, token_for, w["owner"], w["farm_a"], **extra).status_code == 422
    assert jobs() == before


def test_given_a_queued_job_then_no_download_is_offered_and_file_keys_are_never_exposed(client, token_for, world):
    w = world
    created = request(client, token_for, w["owner"], w["farm_a"])
    assert set(created.json()) == {"id", "state", "row_count"}
    r = status(client, token_for, w["owner"], w["farm_a"], created.json()["id"])
    assert r.status_code == 200 and r.json()["downloads"] == {} and "file_keys" not in r.text and "download_url" not in r.json()
    assert sql("SELECT file_keys FROM export_jobs WHERE id=$1", uuid.UUID(created.json()["id"]))[0][0] is None  # only the worker names files


def test_given_a_finished_job_when_the_requester_reads_it_then_short_signed_urls_for_the_server_keys_are_issued(client, token_for, world):
    w = world
    job = add_job(w["farm_a"], w["owner"])
    r = status(client, token_for, w["owner"], w["farm_a"], job)
    assert r.status_code == 200, r.text
    assert r.headers["Cache-Control"] == "no-store"
    body = r.json()
    assert body["state"] == "done" and set(body["downloads"]) == {"pdf", "xlsx"} and "file_keys" not in r.text
    for fmt, url in body["downloads"].items():
        u = urlparse(url)
        q = parse_qs(u.query)
        assert u.hostname == urlparse(os.environ["S3_ENDPOINT"]).hostname  # hosted with the stack (Morocco), never a foreign domain
        assert f"/farms/{w['farm_a']}/exports/{job}/" in u.path and u.path.endswith("." + fmt)
        assert 0 < int(q["X-Amz-Expires"][0]) <= 900 and "X-Amz-Signature" in q
        got = httpx.get(url, timeout=10)
        assert got.status_code == 200 and got.content.startswith(b"%PDF" if fmt == "pdf" else b"PK")


def test_given_a_signed_url_then_it_cannot_reach_another_object(client, token_for, world):
    w = world
    job = add_job(w["farm_a"], w["owner"])
    other = f"farms/{w['farm_b']}/exports/{uuid.uuid4()}/secret.pdf"
    put(other, b"%PDF-secret")
    url = status(client, token_for, w["owner"], w["farm_a"], job).json()["downloads"]["pdf"]
    forged = url.replace(f"farms/{w['farm_a']}/exports/{job}/", f"farms/{w['farm_b']}/exports/{other.split('/')[3]}/").replace("registry.pdf", "secret.pdf")
    assert httpx.get(forged, timeout=10).status_code in (403, 404)


def test_given_a_finished_job_when_another_user_reads_it_then_no_url_is_issued_to_them(client, token_for, world):
    w = world
    job = add_job(w["farm_a"], w["owner"])
    ghost = status(client, token_for, w["owner"], w["farm_a"], uuid.uuid4())
    for who in ("manager", "owner_b", "outsider"):
        r = status(client, token_for, w[who], w["farm_a"], job)
        assert r.status_code == 404 and r.json() == ghost.json() and "X-Amz" not in r.text


def test_given_a_job_whose_stored_key_points_outside_its_farm_then_no_url_is_signed(client, token_for, world):
    w = world
    foreign = f"farms/{w['farm_b']}/exports/{uuid.uuid4()}/registry.pdf"
    put(foreign, b"%PDF-secret")
    job = add_job(w["farm_a"], w["owner"], fmt="pdf", keys={"pdf": foreign})
    r = status(client, token_for, w["owner"], w["farm_a"], job)
    assert r.status_code == 404 and "X-Amz" not in r.text


def test_given_an_expired_or_failed_job_then_no_url_is_issued(client, token_for, world):
    w = world
    old = add_job(w["farm_a"], w["owner"], expires=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1), created=dt.datetime.now(dt.UTC) - dt.timedelta(days=8))
    expired = status(client, token_for, w["owner"], w["farm_a"], old)
    assert expired.status_code == 410 and expired.json()["detail"]["code"] == "export_expired" and "X-Amz" not in expired.text
    failed = add_job(w["farm_a"], w["owner"], state="failed", files=False)
    r = status(client, token_for, w["owner"], w["farm_a"], failed)
    assert r.status_code == 200 and r.json()["state"] == "failed" and r.json()["downloads"] == {}


def test_given_the_export_routes_then_no_external_connection_is_attempted(client, token_for, world, monkeypatch):
    w = world
    job = add_job(w["farm_a"], w["owner"])
    real = socket.create_connection

    def guarded(addr, *a, **k):
        assert addr[0] in ("minio", "db", "redis", "testserver", "localhost", "127.0.0.1"), addr
        return real(addr, *a, **k)

    monkeypatch.setattr(socket, "create_connection", guarded)
    assert status(client, token_for, w["owner"], w["farm_a"], job).status_code == 200

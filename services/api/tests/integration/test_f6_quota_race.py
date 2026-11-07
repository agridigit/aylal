"""T017 - G3: quotas are counted under a per-farm advisory lock, in the same transaction as the write."""
import datetime as dt
import pathlib
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, op_body, sync_op, world  # noqa: F401

APP = pathlib.Path(__file__).resolve().parents[2] / "app"
LOCK = "pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"


def _seed_ops(farm, author, parcel, n, status):
    year = TODAY.year
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) "
        "SELECT gen_random_uuid(), $1, 'irrigation', make_date($5, 1, 1) + (g % 300), $4, $2 FROM generate_series(1, $3) g",
        farm, author, n, status, year)
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", farm)[0][0] == n


def _race(n, fn):
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(lambda _: fn(), range(n)))


def _rest(w, token, body_factory):
    from app.main import app

    def one():
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token), json=body_factory()).status_code
    return one


def test_given_the_service_then_the_lock_precedes_counting_and_writing():
    text = (APP / "operations" / "service.py").read_text(encoding="utf-8")
    assert LOCK in text
    assert text.index(LOCK) < text.index("count(")


def test_given_one_slot_left_in_the_yearly_quota_when_two_rest_requests_race_then_exactly_one_passes(client, token_for, world):
    w = world
    _seed_ops(w["farm_a"], w["owner"], w["a1"], 19_999, "validated")
    codes = _race(2, _rest(w, token_for(w["owner"]), lambda: op_body([w["a1"]])))
    assert sorted(codes)[0] == 201 and codes.count(201) == 1, codes
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", w["farm_a"])[0][0] == 20_000


def test_given_one_slot_left_in_the_yearly_quota_when_two_sync_uploads_race_then_exactly_one_passes(client, token_for, world):
    w = world
    _seed_ops(w["farm_a"], w["owner"], w["a1"], 19_999, "validated")
    tok = token_for(w["owner"])
    from app.main import app

    def one():
        with TestClient(app) as c:
            body = {"ops": [sync_op("operations", w["farm_a"], uuid.uuid4(), {
                "type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]})]}
            r = c.post("/v1/sync/upload", headers=auth(tok), json=body)
            return r.status_code, (r.json()["results"][0]["status"] if r.status_code == 200 else None)
    results = _race(2, one)
    assert sum(1 for c, s in results if c == 200 and s != "rejected") == 1, results
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", w["farm_a"])[0][0] == 20_000


def test_given_499_planned_operations_when_two_requests_race_then_exactly_one_planned_is_added(client, token_for, world):
    w = world
    _seed_ops(w["farm_a"], w["owner"], w["a1"], 499, "planned")
    future = (TODAY + dt.timedelta(days=5)).isoformat()
    codes = _race(2, _rest(w, token_for(w["owner"]), lambda: op_body([w["a1"]], performed_on=future)))
    assert codes.count(201) == 1, codes
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1 AND status='planned'", w["farm_a"])[0][0] == 500


def test_given_two_concurrent_export_requests_then_one_is_accepted_and_one_active_job_exists(client, token_for, world):
    w = world
    tok = token_for(w["owner"])
    body = {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "pdf", "scope": "farm", "lang": "fr"}
    from app.main import app

    def one():
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=auth(tok), json=body).status_code
    codes = _race(2, one)
    assert codes.count(202) == 1 and set(codes) <= {202, 409, 429}, codes
    assert sql("SELECT count(*) FROM export_jobs WHERE farm_id=$1 AND state IN ('queued','running')", w["farm_a"])[0][0] == 1


def test_given_nine_exports_in_the_last_hour_when_two_race_then_at_most_one_more_is_accepted(client, token_for, world):
    w = world
    sql("INSERT INTO export_jobs (id, farm_id, requested_by, scope, period_from, period_to, format, lang, state, row_count, expires_at, created_at) "
        "SELECT gen_random_uuid(), $1, $2, 'farm', '2026-01-01', '2026-12-31', 'pdf', 'fr', 'done', 0, now() + interval '1 day', now() "
        "FROM generate_series(1, 9)", w["farm_a"], w["owner"])
    tok = token_for(w["owner"])
    body = {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "pdf", "scope": "farm", "lang": "fr"}
    from app.main import app

    def one():
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=auth(tok), json=body).status_code
    codes = _race(2, one)
    assert codes.count(202) == 1, codes


def test_given_a_replayed_sync_operation_then_applied_ops_makes_it_idempotent(client, token_for, world):
    w = world
    rid, op_id = uuid.uuid4(), uuid.uuid4()
    o = sync_op("operations", w["farm_a"], rid, {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]})
    o["op_id"] = str(op_id)
    h = auth(token_for(w["owner"]))
    assert client.post("/v1/sync/upload", headers=h, json={"ops": [o]}).status_code == 200
    assert client.post("/v1/sync/upload", headers=h, json={"ops": [o]}).status_code == 200
    assert sql("SELECT count(*) FROM operations WHERE id=$1", rid)[0][0] == 1
    assert sql("SELECT count(*) FROM applied_ops WHERE op_id=$1", op_id)[0][0] == 1

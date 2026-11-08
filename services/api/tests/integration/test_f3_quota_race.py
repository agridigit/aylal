"""T023 - G4: quotas are counted under a per-farm advisory lock in the same transaction as the write."""
import os
import pathlib
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql
from tests.integration._f3 import seed_zone, sync_obs, world3  # noqa: F401

APP = pathlib.Path(__file__).resolve().parents[2] / "app"
WORKERS = pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "services/workers/tasks"
LOCK = "pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"


def _race(n, fn):
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(lambda _: fn(), range(n)))


def _seed_observations(w, n):
    """n observations on closed zones (<= 20 per zone) so the yearly farm quota is the only limit left."""
    per, zones = 20, (n + 19) // 20
    for i in range(zones):
        z = seed_zone(w["farm_a"], w["p"][3 + i % 6], status="visited")
        k = per if (i + 1) * per <= n else n - i * per
        sql("INSERT INTO zone_observations (id, farm_id, zone_id, parcel_id, author_id, note, created_at)"
            " SELECT gen_random_uuid(), $1, $2, $3, $4, 'n', now() FROM generate_series(1, $5)", w["farm_a"], z, w["p"][3 + i % 6], w["owner"], k)
    assert sql("SELECT count(*) FROM zone_observations WHERE farm_id=$1", w["farm_a"])[0][0] == n


@pytest.mark.parametrize("rel", ["monitoring/service.py", "sync/monitoring.py"])
def test_given_the_code_then_the_lock_precedes_counting_and_writing(rel):
    text = (APP / rel).read_text(encoding="utf-8")
    assert LOCK in text
    assert text.index(LOCK) < text.index("count(")


def test_given_the_workers_then_a_status_recompute_takes_the_monitoring_farm_lock():
    text = (WORKERS / "recompute_status.py").read_text(encoding="utf-8")
    assert "monitoring:" in text and "lock" in text.lower()


def test_given_one_slot_left_in_the_yearly_observation_quota_when_two_rest_requests_race_then_exactly_one_passes(client, token_for, world3):
    from app.main import app

    w = world3
    _seed_observations(w, 1999)
    z = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["owner"])

    def one():
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/zones/{z}/observations", headers=auth(tok), json={"id": str(uuid.uuid4()), "note": "x"}).status_code

    codes = _race(2, one)
    assert codes.count(201) == 1 and all(c in (201, 422, 429) for c in codes), codes
    assert sql("SELECT count(*) FROM zone_observations WHERE farm_id=$1", w["farm_a"])[0][0] == 2000


def test_given_one_slot_left_in_the_yearly_observation_quota_when_two_sync_uploads_race_then_exactly_one_is_applied(client, token_for, world3):
    from app.main import app

    w = world3
    _seed_observations(w, 1999)
    z = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["owner"])

    def one():
        with TestClient(app) as c:
            r = c.post("/v1/sync/upload", headers=auth(tok), json={"ops": [sync_obs(w["farm_a"], z)]})
            return r.status_code, (r.json()["results"][0]["status"] if r.status_code == 200 else None)

    out = _race(2, one)
    assert [s for _, s in out].count("applied") == 1, out
    assert sql("SELECT count(*) FROM zone_observations WHERE farm_id=$1", w["farm_a"])[0][0] == 2000


def test_given_two_reprocess_jobs_already_today_when_two_requests_race_then_exactly_one_is_accepted(client, token_for, world3):
    from app.main import app

    w = world3
    for _ in range(2):
        sql("INSERT INTO monitoring_jobs (id, farm_id, parcel_id, kind, state, requested_by, started_at) VALUES (gen_random_uuid(),$1,$2,'reprocess','done',$3,now())",
            w["farm_a"], w["a1"], w["owner"])
    tok = token_for(w["owner"])

    def one():
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/vigor/reprocess", headers=auth(tok)).status_code

    codes = _race(2, one)
    assert sorted(codes) == [202, 429], codes


def test_given_four_imagery_jobs_on_the_farm_when_two_requests_race_on_two_parcels_then_exactly_one_is_accepted(client, token_for, world3):
    from app.main import app

    w = world3
    for i in range(4):
        sql("INSERT INTO monitoring_jobs (id, farm_id, parcel_id, kind, state, requested_by) VALUES (gen_random_uuid(),$1,$2,'reprocess','running',$3)",
            w["farm_a"], w["p"][6 + i % 3], w["owner"])
    tok = token_for(w["owner"])
    targets = [w["p"][3], w["p"][4]]
    it = iter(targets)

    def one():
        p = next(it)
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/parcels/{p}/vigor/reprocess", headers=auth(tok)).status_code

    codes = _race(2, one)
    assert sorted(codes) == [202, 429], codes

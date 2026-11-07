"""Security finding: the 500 active fields cap must hold on restore, under concurrency and on sync upload (REST/sync parity)."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.helpers import auth, op, sql
from tests.integration._f2 import add_block, add_field, new_user, square

FAR = json.dumps(square(-6.0))


def fill(farm, active, archived=0):
    sql("INSERT INTO parcels (id, farm_id, name, geometry) SELECT gen_random_uuid(), $1, 'F'||g, ST_SetSRID(ST_GeomFromGeoJSON($2), 4326) FROM generate_series(1, $3) g", farm, FAR, active)
    sql("INSERT INTO parcels (id, farm_id, name, geometry, archived_at, purge_after) SELECT gen_random_uuid(), $1, 'A'||g, ST_SetSRID(ST_GeomFromGeoJSON($2), 4326), now(), now() + interval '90 days' FROM generate_series(1, $3) g", farm, FAR, archived)


def active(farm):
    return sql("SELECT count(*) FROM parcels WHERE farm_id=$1 AND archived_at IS NULL", farm)[0][0]


@pytest.fixture
def w(make_farm, token_for):
    owner = new_user()
    return dict(farm=make_farm({owner: "owner"}), h=auth(token_for(owner)))


def archived_ids(farm):
    return [r[0] for r in sql("SELECT id FROM parcels WHERE farm_id=$1 AND archived_at IS NOT NULL ORDER BY name", farm)]


def restore(client, w, fid):
    return client.post(f"/v1/farms/{w['farm']}/fields/{fid}/restore", headers=w["h"])


def parcel_put(farm, i):
    o = op(farm, uuid.uuid4(), kind="put", fields={"name": f"S{i}", "geometry": square(-7.9 + i * 0.003)})
    o["table"] = "parcels"
    return o


def test_given_500_active_fields_when_restoring_an_archived_one_then_422_field_limit_reached_and_it_stays_archived(client, w):
    fill(w["farm"], 500, 1)
    (fid,) = archived_ids(w["farm"])
    r = restore(client, w, fid)
    assert r.status_code == 422 and "field_limit_reached" in r.text
    assert active(w["farm"]) == 500 and sql("SELECT archived_at FROM parcels WHERE id=$1", fid)[0][0] is not None


def test_given_499_active_fields_when_restoring_one_then_200_and_the_cap_is_reached_exactly(client, w):
    fill(w["farm"], 499, 2)
    first, second = archived_ids(w["farm"])
    assert restore(client, w, first).status_code == 200 and active(w["farm"]) == 500
    assert restore(client, w, second).status_code == 422


def test_given_499_active_fields_when_restoring_in_parallel_then_never_more_than_500_are_active(client, w):
    fill(w["farm"], 499, 6)
    with ThreadPoolExecutor(6) as pool:
        codes = list(pool.map(lambda f: restore(client, w, f).status_code, archived_ids(w["farm"])))
    assert sorted(codes) == [200] + [422] * 5, codes
    assert active(w["farm"]) == 500


def test_given_an_archived_field_when_restoring_through_a_sync_patch_then_it_is_refused_and_stays_archived(client, w):
    fill(w["farm"], 500, 1)
    (fid,) = archived_ids(w["farm"])
    o = op(w["farm"], fid, kind="patch", fields={"archived_at": None})
    o["table"] = "parcels"
    r = client.post("/v1/sync/upload", json={"ops": [o]}, headers=w["h"])
    assert r.status_code == 404 or r.json()["results"][0]["status"] == "rejected"
    assert active(w["farm"]) == 500


def test_given_500_active_fields_when_splitting_into_blocks_then_the_split_still_works_and_creates_no_field(client, w):
    """Splitting = blocks inside a field (R9): it never creates a field, so it cannot bypass the cap."""
    fid = add_field(w["farm"], "Big")
    fill(w["farm"], 499)
    r = client.post(f"/v1/farms/{w['farm']}/fields/{fid}/blocks", json={"name": "N", "kind": "block", "geometry": square(-7.60, 33.57, 0.0009)}, headers=w["h"])
    assert r.status_code == 201 and active(w["farm"]) == 500
    assert add_block(w["farm"], fid) and active(w["farm"]) == 500


def test_given_499_active_fields_when_creating_in_parallel_then_exactly_one_succeeds_and_500_is_never_exceeded(client, w):
    fill(w["farm"], 499)

    def create(i):
        return client.post(f"/v1/farms/{w['farm']}/fields", json={"name": f"P{i}", "geometry": square(-7.9 + i * 0.003)}, headers=w["h"]).status_code

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(create, range(8)))
    assert sorted(codes) == [201] + [422] * 7, codes
    assert active(w["farm"]) == 500


def test_given_499_active_fields_when_a_sync_batch_creates_three_then_only_one_is_applied_and_the_others_rejected(client, w):
    fill(w["farm"], 499)
    r = client.post("/v1/sync/upload", json={"ops": [parcel_put(w["farm"], i) for i in range(3)]}, headers=w["h"])
    results = r.json()["results"]
    assert [x["status"] for x in results] == ["applied", "rejected", "rejected"]
    assert all(x["error"]["code"] == "field_limit_reached" for x in results[1:])
    assert active(w["farm"]) == 500


def test_given_499_active_fields_when_parallel_sync_uploads_create_fields_then_500_is_never_exceeded(client, w):
    fill(w["farm"], 499)

    def upload(i):
        return client.post("/v1/sync/upload", json={"ops": [parcel_put(w["farm"], i)]}, headers=w["h"]).json()["results"][0]["status"]

    with ThreadPoolExecutor(8) as pool:
        statuses = list(pool.map(upload, range(8)))
    assert sorted(statuses) == ["applied"] + ["rejected"] * 7, statuses
    assert active(w["farm"]) == 500

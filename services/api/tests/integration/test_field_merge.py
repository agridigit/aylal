"""T058 - merge fields (R5-A2): cumulated area, history kept, contiguity, atomicity, idempotent field_commands."""
import datetime as dt
import json
import uuid

import pytest

from tests.helpers import auth, op, sql
from tests.integration._f2 import add_block, add_field, assign, new_user, reference_crop

EDGE = -7.60 + 0.002  # west edge of B == east edge of A (same float as the square corner)


@pytest.fixture
def w(make_farm, token_for):
    owner, worker, stranger = new_user(), new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    other = make_farm({stranger: "owner"})
    a, b, far = add_field(farm, "A"), add_field(farm, "B", lon=EDGE), add_field(farm, "Far", lon=-7.0)
    assign(farm, worker, b)
    return dict(farm=farm, other=other, a=a, b=b, far=far, foreign=add_field(other, "X"),
                h=auth(token_for(owner)), hw=auth(token_for(worker)), hs=auth(token_for(stranger)), crop=reference_crop(),
                crop2=sql("SELECT id FROM crops WHERE farm_id IS NULL ORDER BY slug OFFSET 1 LIMIT 1")[0][0])


def merge(client, w, survivor, merged, headers=None, farm=None):
    return client.post(f"/v1/farms/{farm or w['farm']}/fields/merge", json={"survivor_id": str(survivor), "merged_ids": [str(m) for m in merged]}, headers=headers or w["h"])


def season(farm, field, crop, start, end=None):
    sid = uuid.uuid4()
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, ended_at) VALUES ($1,$2,$3,$4,$5,$6)", sid, farm, field, crop, dt.date.fromisoformat(start), dt.date.fromisoformat(end) if end else None)
    return sid


def area(fid):
    return float(sql("SELECT ST_Area(geometry::geography)/10000 FROM parcels WHERE id=$1", fid)[0][0])


def test_given_two_contiguous_fields_when_merging_then_one_field_with_the_cumulated_area_replaces_them(client, w):
    total = area(w["a"]) + area(w["b"])
    r = merge(client, w, w["a"], [w["b"]])
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(w["a"]) and float(r.json()["area_calc_ha"]) == pytest.approx(total, rel=0.005)
    archived = sql("SELECT archived_at, merged_into_id, purge_after FROM parcels WHERE id=$1", w["b"])[0]
    assert archived[0] is not None and archived[1] == w["a"] and archived[2] is not None
    active = client.get(f"/v1/farms/{w['farm']}/fields", headers=w["h"]).json()["items"]
    assert {x["id"] for x in active} == {str(w["a"]), str(w["far"])}


def test_given_seasons_on_both_fields_when_merging_then_history_is_kept_and_attached_to_the_survivor(client, w):
    closed = season(w["farm"], w["b"], w["crop"], "2023-10-01", "2024-06-01")
    other_crop = season(w["farm"], w["b"], w["crop2"], "2025-01-01")
    own = season(w["farm"], w["a"], w["crop"], "2025-10-01")
    assert merge(client, w, w["a"], [w["b"]]).status_code == 200
    rows = {r[0]: r for r in sql("SELECT id, field_id, ended_at, parcel_archived_at FROM seasons WHERE farm_id=$1", w["farm"])}
    assert set(rows) == {closed, other_crop, own}  # nothing deleted
    assert all(r[1] == w["a"] and r[3] is None for r in rows.values())  # denormalised column follows: no PowerSync join needed
    listed = client.get(f"/v1/farms/{w['farm']}/fields/{w['a']}/seasons", headers=w["h"]).json()["items"]
    assert {s["id"] for s in listed} == {str(closed), str(other_crop), str(own)}


def test_given_the_same_active_crop_on_both_fields_when_merging_then_the_oldest_is_kept_and_the_other_is_closed_not_deleted(client, w):
    old = season(w["farm"], w["b"], w["crop"], "2025-01-01")
    new = season(w["farm"], w["a"], w["crop"], "2026-01-01")
    assert merge(client, w, w["a"], [w["b"]]).status_code == 200
    rows = {r[0]: r for r in sql("SELECT id, field_id, ended_at FROM seasons WHERE farm_id=$1", w["farm"])}
    assert rows[old][1] == w["a"] and rows[old][2] is None
    assert rows[new][2] is not None  # closed, kept for history
    assert sql("SELECT count(*) FROM seasons WHERE field_id=$1 AND crop_id=$2 AND ended_at IS NULL", w["a"], w["crop"])[0][0] == 1


def test_given_blocks_and_a_worker_assignment_on_the_merged_field_when_merging_then_they_follow_the_survivor(client, w):
    bid = add_block(w["farm"], w["b"])
    assert merge(client, w, w["a"], [w["b"]]).status_code == 200
    row = sql("SELECT field_id, parcel_archived_at, archived_at FROM field_blocks WHERE id=$1", bid)[0]
    assert row[0] == w["a"] and row[1] is None and row[2] is None
    assert sql("SELECT parcel_id FROM worker_parcels WHERE farm_id=$1", w["farm"])[0][0] == w["a"]


def test_given_non_contiguous_fields_when_merging_then_422_and_nothing_changes(client, w):
    sid = season(w["farm"], w["far"], w["crop"], "2025-01-01")
    r = merge(client, w, w["a"], [w["far"]])
    assert r.status_code == 422 and "merge_not_contiguous" in r.text
    assert sql("SELECT count(*) FROM parcels WHERE farm_id=$1 AND archived_at IS NULL", w["farm"])[0][0] == 3
    assert sql("SELECT field_id FROM seasons WHERE id=$1", sid)[0][0] == w["far"]


def test_given_one_unknown_field_among_three_when_merging_then_404_and_the_others_are_untouched(client, w):
    before = area(w["a"])
    r = merge(client, w, w["a"], [w["b"], uuid.uuid4()])
    assert r.status_code == 404
    assert area(w["a"]) == before and sql("SELECT archived_at FROM parcels WHERE id=$1", w["b"])[0][0] is None


def test_given_fewer_than_two_distinct_fields_when_merging_then_422(client, w):
    assert merge(client, w, w["a"], []).status_code == 422
    assert merge(client, w, w["a"], [w["a"]]).status_code == 422


def test_given_a_field_of_another_farm_when_merging_then_404_without_leak(client, w):
    assert merge(client, w, w["a"], [w["foreign"]]).status_code == 404
    assert merge(client, w, w["foreign"], [w["a"]]).status_code == 404
    ghost = merge(client, w, w["a"], [w["b"]], headers=w["hs"], farm=uuid.uuid4())
    mine = merge(client, w, w["a"], [w["b"]], headers=w["hs"])
    assert ghost.status_code == mine.status_code == 404 and ghost.content == mine.content


def test_given_an_archived_field_when_merging_it_then_404(client, w):
    sql("UPDATE parcels SET archived_at=now(), purge_after=now()+interval '90 days' WHERE id=$1", w["b"])
    assert merge(client, w, w["a"], [w["b"]]).status_code == 404
    assert merge(client, w, w["b"], [w["a"]]).status_code == 404


def test_given_a_worker_when_merging_then_403_and_nothing_changes(client, w):
    assert merge(client, w, w["a"], [w["b"]], headers=w["hw"]).status_code == 403
    assert sql("SELECT archived_at FROM parcels WHERE id=$1", w["b"])[0][0] is None


def test_given_a_merged_field_when_restoring_it_within_90_days_then_it_is_active_again_without_merged_into(client, w):
    assert merge(client, w, w["a"], [w["b"]]).status_code == 200
    r = client.post(f"/v1/farms/{w['farm']}/fields/{w['b']}/restore", headers=w["h"])
    assert r.status_code == 200 and sql("SELECT merged_into_id FROM parcels WHERE id=$1", w["b"])[0][0] is None


# ---- offline command replayed through /v1/sync/upload ----

def command(w, payload=None, rid=None, op_id=None):
    o = op(w["farm"], rid or uuid.uuid4(), kind="put", op_id=op_id,
           fields={"kind": "merge", "payload": payload or {"survivor_id": str(w["a"]), "merged_ids": [str(w["b"])]}})
    o["table"] = "field_commands"
    return o


def upload(client, headers, *ops):
    r = client.post("/v1/sync/upload", json={"ops": list(ops)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["results"]


def test_given_a_merge_command_when_synced_twice_then_it_is_applied_once_and_recorded(client, w):
    season(w["farm"], w["b"], w["crop"], "2025-01-01")
    total = area(w["a"]) + area(w["b"])
    o = command(w)
    assert upload(client, w["h"], o)[0]["status"] == "applied"
    assert upload(client, w["h"], o)[0]["status"] == "duplicate"
    assert area(w["a"]) == pytest.approx(total, rel=0.005)
    rows = sql("SELECT kind, result, created_by FROM field_commands WHERE farm_id=$1", w["farm"])
    assert len(rows) == 1 and rows[0][0] == "merge" and json.loads(rows[0][1]) == {"ok": True}
    assert sql("SELECT field_id FROM seasons WHERE farm_id=$1", w["farm"])[0][0] == w["a"]


def test_given_a_non_contiguous_merge_command_when_synced_then_it_is_rejected_recorded_and_nothing_else_changes(client, w):
    res = upload(client, w["h"], command(w, {"survivor_id": str(w["a"]), "merged_ids": [str(w["far"])]}))[0]
    assert res["status"] == "rejected" and res["error"]["code"] == "merge_not_contiguous"
    row = sql("SELECT result FROM field_commands WHERE farm_id=$1", w["farm"])[0]
    assert json.loads(row[0])["error"]["code"] == "merge_not_contiguous"
    assert sql("SELECT count(*) FROM parcels WHERE farm_id=$1 AND archived_at IS NULL", w["farm"])[0][0] == 3


def test_given_a_command_in_a_batch_with_a_failing_op_when_synced_then_only_the_failing_op_is_rejected(client, w):
    bad = command(w, {"survivor_id": str(w["a"]), "merged_ids": [str(uuid.uuid4())]})
    res = upload(client, w["h"], bad, command(w))
    assert [r["status"] for r in res] == ["rejected", "applied"]


def test_given_the_same_command_id_with_a_new_op_when_synced_then_commands_are_insert_only(client, w):
    rid = uuid.uuid4()
    assert upload(client, w["h"], command(w, rid=rid))[0]["status"] == "applied"
    again = upload(client, w["h"], command(w, rid=rid))[0]
    assert again["status"] == "rejected"
    assert sql("SELECT count(*) FROM field_commands WHERE id=$1", rid)[0][0] == 1


def test_given_a_worker_or_a_stranger_when_syncing_a_merge_command_then_403_or_404_and_nothing_is_written(client, w):
    r = client.post("/v1/sync/upload", json={"ops": [command(w)]}, headers=w["hw"])
    assert r.status_code == 403
    r = client.post("/v1/sync/upload", json={"ops": [command(w)]}, headers=w["hs"])
    assert r.status_code == 404
    assert sql("SELECT count(*) FROM field_commands")[0][0] == 0


def test_given_a_command_naming_a_field_of_another_farm_when_synced_then_it_is_rejected_not_found_and_nothing_moves(client, w):
    res = upload(client, w["h"], command(w, {"survivor_id": str(w["a"]), "merged_ids": [str(w["foreign"])]}))[0]
    assert res["status"] == "rejected" and res["error"]["code"] == "not_found"
    assert sql("SELECT archived_at FROM parcels WHERE id=$1", w["foreign"])[0][0] is None

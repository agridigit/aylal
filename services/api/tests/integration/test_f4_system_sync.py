"""T049 (US1) - R1-A4: an installation written offline is replayed without loss and idempotently (real PostgreSQL, /v1/sync/upload)."""
import uuid

from tests.helpers import sql
from tests.integration._f2 import add_field
from tests.integration._f4 import call, sync_op, sync_post, world4  # noqa: F401

FIELDS = {"kind": "drip", "sectors_count": 2, "emitter_flow_lph": 4, "emitter_spacing_m": 0.5, "row_spacing_m": 2}


def _op(w, parcel, rid=None, op_id=None, **extra):
    return sync_op("irrigation_systems", w["farm_a"], rid or uuid.uuid4(), {"parcel_id": str(parcel), **FIELDS, **extra}, op_id=op_id)


def _parcel(w, name="Off"):
    parcel = add_field(w["farm_a"], name, lon=-7.30)
    sql("UPDATE parcels SET irrigation='drip' WHERE id=$1", parcel)
    return parcel


def test_given_a_system_described_offline_when_replayed_then_it_is_stored_with_a_version_and_a_server_version(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    parcel = _parcel(w)
    r = sync_post(client, token_for(w["owner"]), [_op(w, parcel, rid)])
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "applied", r.text
    assert sql("SELECT parcel_id, kind FROM irrigation_systems WHERE id=$1", rid)[0]["parcel_id"] == parcel
    assert sql("SELECT count(*) FROM irrigation_system_versions WHERE system_id=$1", rid)[0][0] == 1
    assert call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation-system").json()["efficiency_effective"] == 0.9


def test_given_the_same_operation_replayed_twice_then_it_is_a_duplicate_and_nothing_is_added(client, token_for, world4):
    w = world4
    parcel, op_id, rid = _parcel(w), uuid.uuid4(), uuid.uuid4()
    tok = token_for(w["owner"])
    assert sync_post(client, tok, [_op(w, parcel, rid, op_id)]).json()["results"][0]["status"] == "applied"
    again = sync_post(client, tok, [_op(w, parcel, rid, op_id)])
    assert again.status_code == 200 and again.json()["results"][0]["status"] == "duplicate"
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 1
    assert sql("SELECT count(*) FROM irrigation_system_versions WHERE system_id=$1", rid)[0][0] == 1


def test_given_two_members_editing_the_same_system_offline_then_the_last_write_wins_and_both_versions_stay_in_the_history(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    parcel = _parcel(w)
    assert sync_post(client, token_for(w["owner"]), [_op(w, parcel, rid)]).status_code == 200
    first = sync_post(client, token_for(w["owner"]), [_op(w, parcel, rid, emitter_flow_lph=6)])
    last = sync_post(client, token_for(w["manager"]), [_op(w, parcel, rid, emitter_flow_lph=8)])
    assert first.status_code == last.status_code == 200
    assert float(sql("SELECT emitter_flow_lph FROM irrigation_systems WHERE id=$1", rid)[0][0]) == 8
    assert sql("SELECT count(*) FROM irrigation_system_versions WHERE system_id=$1", rid)[0][0] == 3
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 1


def test_given_an_incoherent_value_offline_then_the_operation_is_rejected_with_the_field_and_nothing_is_stored(client, token_for, world4):
    w = world4
    parcel = _parcel(w)
    r = sync_post(client, token_for(w["owner"]), [_op(w, parcel, emitter_flow_lph=0)])
    res = r.json()["results"][0]
    assert r.status_code == 200 and res["status"] == "rejected" and res["error"]["field"] == "emitter_flow_lph", r.text
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 0


def test_given_a_server_field_in_the_payload_then_it_is_ignored_or_rejected_and_never_written(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    parcel = _parcel(w)
    r = sync_post(client, token_for(w["owner"]), [_op(w, parcel, rid, farm_id=str(w["farm_b"]), server_version=99)])
    assert r.status_code == 200 and r.json()["results"][0]["status"] in ("applied", "rejected"), r.text
    assert sql("SELECT count(*) FROM irrigation_systems WHERE id=$1 AND (farm_id <> $2 OR server_version = 99)", rid, w["farm_a"])[0][0] == 0


def test_given_another_farm_when_uploading_for_this_farm_then_404_and_nothing_is_written(client, token_for, world4):
    w = world4
    parcel = _parcel(w)
    r = sync_post(client, token_for(w["owner_b"]), [_op(w, parcel)])
    assert r.status_code == 404
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 0

"""T024 - a field drawn offline is replayed through /v1/sync/upload (R1-A1, idempotence, conflict without loss)."""
import uuid

import pytest

from tests.helpers import auth, op, sql
from tests.integration._f2 import new_user, square


@pytest.fixture
def ctx(make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    return dict(farm=farm, h=auth(token_for(owner)))


def parcel_op(farm, fid, kind="put", fields=None, base_version=0, **kw):
    o = op(farm, fid, kind=kind, fields=fields or {}, base_version=base_version, **kw)
    o["table"] = "parcels"
    return o


def upload(client, ctx, *ops):
    r = client.post("/v1/sync/upload", json={"ops": list(ops)}, headers=ctx["h"])
    assert r.status_code == 200, r.text
    return r.json()["results"]


def test_given_a_gps_field_created_offline_when_syncing_then_it_exists_with_the_client_uuid_and_a_server_computed_area(client, ctx):
    fid = uuid.uuid4()
    (res,) = upload(client, ctx, parcel_op(ctx["farm"], fid, fields={
        "name": "GPS", "geometry": square(), "source": "draw_gps", "gps_accuracy_m": 6, "area_calc_ha": 12345}))
    assert res["status"] == "applied"
    area, source = sql("SELECT area_calc_ha, source FROM parcels WHERE id=$1", fid)[0]
    assert source == "draw_gps" and 0 < float(area) < 100  # the client value 12345 never lands


def test_given_the_same_creation_replayed_when_syncing_then_no_duplicate_field_exists(client, ctx):
    fid, op_id = uuid.uuid4(), uuid.uuid4()
    o = parcel_op(ctx["farm"], fid, fields={"name": "Once", "geometry": square()}, op_id=op_id)
    assert upload(client, ctx, o)[0]["status"] == "applied"
    assert upload(client, ctx, o)[0]["status"] == "duplicate"
    assert sql("SELECT count(*) FROM parcels WHERE id=$1", fid)[0][0] == 1


def test_given_an_invalid_drawing_in_a_batch_when_syncing_then_only_that_operation_is_rejected(client, ctx):
    good, bad = uuid.uuid4(), uuid.uuid4()
    paris = parcel_op(ctx["farm"], bad, fields={"name": "Paris", "geometry": square(2.35, 48.85)})
    results = upload(client, ctx, parcel_op(ctx["farm"], good, fields={"name": "Ok", "geometry": square()}), paris)
    assert [r["status"] for r in results] == ["applied", "rejected"]
    assert results[1]["error"]["code"] == "outside_morocco"
    assert sql("SELECT count(*) FROM parcels WHERE id=$1", bad)[0][0] == 0


def test_given_two_devices_editing_the_same_field_name_when_the_second_syncs_then_the_conflict_is_logged_and_nothing_is_lost(client, ctx):
    fid = uuid.uuid4()
    upload(client, ctx, parcel_op(ctx["farm"], fid, fields={"name": "Base", "geometry": square()}))
    v1 = sql("SELECT server_version FROM parcels WHERE id=$1", fid)[0][0]
    upload(client, ctx, parcel_op(ctx["farm"], fid, "patch", {"name": "Device A"}, base_version=v1))
    (res,) = upload(client, ctx, parcel_op(ctx["farm"], fid, "patch", {"name": "Device B"}, base_version=v1))
    assert res["status"] == "conflict_logged"
    (c,) = sql("SELECT field, discarded_value, kept_value FROM sync_conflicts WHERE record_id=$1", fid)
    assert c["field"] == "name" and "Device A" in str(c["discarded_value"]) and "Device B" in str(c["kept_value"])


def test_given_two_devices_editing_different_fields_when_the_second_syncs_then_both_edits_merge_without_conflict(client, ctx):
    fid = uuid.uuid4()
    upload(client, ctx, parcel_op(ctx["farm"], fid, fields={"name": "Base", "geometry": square()}))
    v1 = sql("SELECT server_version FROM parcels WHERE id=$1", fid)[0][0]
    upload(client, ctx, parcel_op(ctx["farm"], fid, "patch", {"name": "Renamed"}, base_version=v1))
    (res,) = upload(client, ctx, parcel_op(ctx["farm"], fid, "patch", {"irrigation": "drip"}, base_version=v1))
    assert res["status"] == "applied"
    assert sql("SELECT name, irrigation FROM parcels WHERE id=$1", fid)[0][:] == ("Renamed", "drip")
    assert sql("SELECT count(*) FROM sync_conflicts WHERE record_id=$1", fid)[0][0] == 0

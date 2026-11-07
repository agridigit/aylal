"""T007 - same access control on /v1/sync/upload for F2 tables (guardrails 3 and 4)."""
import uuid

import pytest

from tests.helpers import auth, op, sql
from tests.integration._f2 import (
    add_block, add_custom_crop, add_field, add_season, assign, new_user, reference_crop, square,
)

F2_PUTS = {
    "parcels": lambda w: dict(name="Synced", geometry=square(-7.8)),
    "seasons": lambda w: dict(field_id=str(w["field_a"]), crop_id=str(reference_crop()), started_at="2026-01-01"),
    "field_blocks": lambda w: dict(field_id=str(w["field_a"]), name="b", kind="block", geometry=square(-7.6, 33.57, 0.0005)),
    "crops": lambda w: dict(name_fr="Safran", name_ary="x", name_ar="x", cycle="annual"),
    "field_commands": lambda w: dict(kind="merge", payload={"survivor_id": str(w["field_a"]), "merged_ids": []}),
}


@pytest.fixture
def world(make_farm):
    owner_a, owner_b, worker = new_user(), new_user(), new_user()
    farm_a, farm_b = make_farm({owner_a: "owner", worker: "worker"}), make_farm({owner_b: "owner"})
    field_a, field_b = add_field(farm_a, "A"), add_field(farm_b, "B", lon=-7.5)
    assign(farm_a, worker, field_a)
    return dict(owner_a=owner_a, owner_b=owner_b, worker=worker, farm_a=farm_a, farm_b=farm_b,
                field_a=field_a, field_b=field_b, outsider=new_user())


def f2op(table, farm, rid, w, kind="put", fields=None):
    o = op(farm, rid, kind=kind, fields=fields if fields is not None else F2_PUTS[table](w))
    o["table"] = table
    return o


def post(client, token_for, who, ops):
    return client.post("/v1/sync/upload", json={"ops": ops}, headers=auth(token_for(who)))


def counts():
    return {t: sql(f"SELECT count(*) FROM {t}")[0][0] for t in F2_PUTS}


@pytest.mark.parametrize("table", list(F2_PUTS))
def test_given_a_worker_when_uploading_an_f2_operation_then_403_for_the_whole_batch_and_nothing_is_written(client, token_for, world, table):
    w = world
    before = counts()
    kept = op(w["farm_a"], uuid.uuid4(), kind="put", fields={"title": "ok"})  # a valid op in the same batch
    r = post(client, token_for, w["worker"], [kept, f2op(table, w["farm_a"], uuid.uuid4(), w)])
    assert r.status_code == 403, r.text
    assert counts() == before
    assert sql("SELECT count(*) FROM trial_records WHERE farm_id=$1", w["farm_a"])[0][0] == 0


@pytest.mark.parametrize("table", list(F2_PUTS))
def test_given_a_non_member_when_uploading_an_f2_operation_then_404_and_nothing_is_written(client, token_for, world, table):
    w = world
    before = counts()
    r = post(client, token_for, w["outsider"], [f2op(table, w["farm_a"], uuid.uuid4(), w)])
    assert r.status_code == 404, r.text
    assert counts() == before


def test_given_an_object_of_another_farm_when_patching_it_through_my_farm_then_404_and_it_is_unchanged(client, token_for, world):
    w = world
    r = post(client, token_for, w["owner_a"], [f2op("parcels", w["farm_a"], w["field_b"], w, "patch", {"name": "Hacked"})])
    assert r.status_code == 404, r.text
    assert sql("SELECT name, farm_id FROM parcels WHERE id=$1", w["field_b"])[0][:] == ("B", w["farm_b"])


def test_given_server_owned_fields_when_a_client_patches_a_field_then_they_are_ignored_but_allowed_fields_apply(client, token_for, world):
    w = world
    sql("UPDATE parcels SET status_summary='ok' WHERE id=$1", w["field_a"])
    area = sql("SELECT area_calc_ha FROM parcels WHERE id=$1", w["field_a"])[0][0]
    created_by = sql("SELECT created_by FROM parcels WHERE id=$1", w["field_a"])[0][0]
    r = post(client, token_for, w["owner_a"], [f2op("parcels", w["farm_a"], w["field_a"], w, "patch", {
        "name": "Renamed", "farm_id": str(w["farm_b"]), "area_calc_ha": 9999, "status_summary": "act",
        "created_by": str(w["owner_b"]), "archived_at": "2026-01-01T00:00:00Z", "purge_after": "2026-01-02T00:00:00Z",
    })])
    assert r.status_code == 200, r.text
    row = sql("SELECT name, farm_id, area_calc_ha, status_summary, created_by, archived_at FROM parcels WHERE id=$1", w["field_a"])[0]
    assert row["name"] == "Renamed"
    assert row["farm_id"] == w["farm_a"]
    assert row["area_calc_ha"] == area and row["status_summary"] == "ok" and row["created_by"] == created_by
    assert row["archived_at"] is None


def test_given_an_archived_field_when_uploading_a_write_on_it_or_its_children_then_refused(client, token_for, world):
    w = world
    season, block = add_season(w["farm_a"], w["field_a"]), add_block(w["farm_a"], w["field_a"])
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["field_a"])
    for table, rid, fields in [("parcels", w["field_a"], {"name": "Late"}), ("seasons", season, {"variety": "Late"}),
                               ("field_blocks", block, {"name": "Late"})]:
        r = post(client, token_for, w["owner_a"], [f2op(table, w["farm_a"], rid, w, "patch", fields)])
        assert r.status_code in (404, 409, 422), f"{table}: {r.status_code} {r.text}"
    assert sql("SELECT name FROM parcels WHERE id=$1", w["field_a"])[0][0] == "A"
    assert sql("SELECT count(*) FROM seasons WHERE variety='Late'")[0][0] == 0
    assert sql("SELECT count(*) FROM field_blocks WHERE name='Late'")[0][0] == 0


def test_given_a_deleted_farm_when_uploading_f2_operations_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    before = counts()
    r = post(client, token_for, w["owner_a"], [f2op("parcels", w["farm_a"], uuid.uuid4(), w)])
    assert r.status_code == 404, r.text
    assert counts() == before

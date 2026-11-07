"""T008 - guardrail 4: a deleted farm (farms.deleted_at) is a 404 on every F2 route and sync write, nothing written."""
import uuid

import pytest

from tests.helpers import auth, op, sql
from tests.integration._f2 import add_block, add_field, add_season, new_user, square


@pytest.fixture
def world(make_farm):
    owner, worker = new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    field = add_field(farm)
    return dict(owner=owner, worker=worker, farm=farm, field=field, block=add_block(farm, field), season=add_season(farm, field))


def _delete(farm):
    sql("UPDATE farms SET deleted_at = now() WHERE id=$1", farm)


def _routes(w):
    f = f"/v1/farms/{w['farm']}"
    return [
        ("GET", f"{f}/fields", None),
        ("POST", f"{f}/fields", {"name": "N", "geometry": square(-7.7)}),
        ("GET", f"{f}/fields/{w['field']}", None),
        ("PATCH", f"{f}/fields/{w['field']}", {"name": "R"}),
        ("GET", f"{f}/fields/archived", None),
        ("GET", f"{f}/fields/{w['field']}/blocks", None),
        ("GET", f"{f}/fields/{w['field']}/seasons", None),
        ("GET", f"{f}/crops", None),
    ]


@pytest.mark.parametrize("who", ["owner", "worker"])
@pytest.mark.parametrize("idx", range(8))
def test_given_a_deleted_farm_when_calling_an_f2_route_then_404_for_every_member(client, token_for, world, who, idx):
    _delete(world["farm"])
    method, path, body = _routes(world)[idx]
    r = client.request(method, path, headers=auth(token_for(world[who])), json=body)
    assert r.status_code == 404, (method, path, r.text)


def test_given_a_deleted_farm_when_the_owner_renames_a_field_then_nothing_changes(client, token_for, world):
    _delete(world["farm"])
    client.patch(f"/v1/farms/{world['farm']}/fields/{world['field']}", headers=auth(token_for(world["owner"])), json={"name": "Hacked"})
    assert sql("SELECT name FROM parcels WHERE id=$1", world["field"])[0][0] == "Field"


@pytest.mark.parametrize("table,fields", [
    ("parcels", {"name": "Hacked"}),
    ("seasons", {"variety": "x"}),
    ("field_blocks", {"name": "x"}),
])
def test_given_a_deleted_farm_when_uploading_an_f2_write_then_404_and_nothing_is_written(client, token_for, world, table, fields):
    _delete(world["farm"])
    rid = {"parcels": world["field"], "seasons": world["season"], "field_blocks": world["block"]}[table]
    before = sql(f"SELECT count(*) FROM {table}")[0][0]
    o = op(world["farm"], rid, fields=fields)
    o["table"] = table
    r = client.post("/v1/sync/upload", json={"ops": [o]}, headers=auth(token_for(world["owner"])))
    assert r.status_code == 404, r.text
    assert sql(f"SELECT count(*) FROM {table}")[0][0] == before
    assert sql("SELECT name FROM parcels WHERE id=$1", world["field"])[0][0] == "Field"


def test_given_a_live_farm_then_the_same_f2_routes_still_answer_for_the_owner(client, token_for, world):
    r = client.get(f"/v1/farms/{world['farm']}/fields", headers=auth(token_for(world["owner"])))
    assert r.status_code == 200


def test_given_a_farm_created_in_the_same_batch_when_adding_a_field_then_the_batch_is_applied(client, token_for):
    user, farm, field = new_user(), uuid.uuid4(), uuid.uuid4()
    farm_op = op(farm, farm, kind="put", fields={"name": "Ma ferme", "location": {"lat": 33.57, "lon": -7.59}})
    farm_op["table"] = "farms"
    field_op = op(farm, field, kind="put", fields={"name": "P1", "geometry": square(-7.59, 33.57, 0.001), "source": "draw_taps"})
    field_op["table"] = "parcels"
    r = client.post("/v1/sync/upload", json={"ops": [farm_op, field_op]}, headers=auth(token_for(user)))
    assert r.status_code == 200, r.text
    assert [x["status"] for x in r.json()["results"]] == ["applied", "applied"]
    assert sql("SELECT created_by FROM parcels WHERE id=$1", field)[0][0] == user

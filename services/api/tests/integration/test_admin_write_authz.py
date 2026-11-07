"""T008a - role check on farm-admin writes, REST and /v1/sync/upload (FR-021, FR-022)."""
import uuid

import pytest

from tests.helpers import auth, op, sql

ADMIN_TABLES = ["worker_parcels", "farm_members", "farms", "invitations"]


@pytest.fixture
def world(make_farm):
    owner, manager, worker, worker2, stranger = (uuid.uuid4() for _ in range(5))
    farm = make_farm({owner: "owner", manager: "manager", worker: "worker", worker2: "worker"})
    other = make_farm({uuid.uuid4(): "owner"})
    parcel = uuid.uuid4()
    sql(
        "INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES"
        " ($1, $2, 'P', ST_GeomFromText('POLYGON((0 0,0 1,1 1,1 0,0 0))', 4326), 0.5)",
        parcel, farm,
    )
    return dict(owner=owner, manager=manager, worker=worker, worker2=worker2, stranger=stranger,
                farm=farm, other=other, parcel=parcel)


def _put(client, token, farm, user, parcels):
    return client.put(f"/v1/farms/{farm}/members/{user}/parcels", headers=auth(token), json={"parcel_ids": [str(p) for p in parcels]})


def _assigned(farm, user):
    return {r[0] for r in sql("SELECT parcel_id FROM worker_parcels WHERE farm_id=$1 AND user_id=$2", farm, user)}


def test_given_a_worker_when_assigning_parcels_via_rest_then_403_and_nothing_is_written(client, token_for, world):
    r = _put(client, token_for(world["worker"]), world["farm"], world["worker2"], [world["parcel"]])
    assert r.status_code == 403
    assert _assigned(world["farm"], world["worker2"]) == set()


@pytest.mark.parametrize("who", ["owner", "manager"])
def test_given_an_owner_or_manager_when_assigning_parcels_then_it_is_accepted(client, token_for, world, who):
    r = _put(client, token_for(world[who]), world["farm"], world["worker"], [world["parcel"]])
    assert r.status_code == 200
    assert _assigned(world["farm"], world["worker"]) == {world["parcel"]}


def test_given_a_non_member_when_assigning_parcels_then_404(client, token_for, world):
    r = _put(client, token_for(world["stranger"]), world["farm"], world["worker"], [])
    assert r.status_code == 404


def test_given_a_member_of_another_farm_when_assigning_parcels_then_404(client, token_for, make_farm, world):
    other_owner = uuid.uuid4()
    mine = make_farm({other_owner: "owner"})
    assert mine != world["farm"]
    r = _put(client, token_for(other_owner), world["farm"], world["worker"], [])
    assert r.status_code == 404


def _admin_op(table, world):
    rid = uuid.uuid4()
    fields = {
        "worker_parcels": {"user_id": str(world["worker"]), "parcel_id": str(world["parcel"])},
        "farm_members": {"user_id": str(world["worker"]), "role": "owner"},
        "farms": {"name": "Hijacked"},
        "invitations": {"phone_e164": "+212612345679", "role": "manager"},
    }[table]
    o = op(world["farm"], rid, kind="put", fields=fields)
    o["table"] = table
    return o


def _farm_state(world):
    return (
        sql("SELECT name FROM farms WHERE id=$1", world["farm"])[0][0],
        sorted((str(r[0]), r[1]) for r in sql("SELECT user_id, role FROM farm_members WHERE farm_id=$1", world["farm"])),
        sql("SELECT count(*) FROM worker_parcels")[0][0],
        sql("SELECT count(*) FROM invitations")[0][0],
    )


@pytest.mark.parametrize("table", ADMIN_TABLES)
def test_given_a_worker_when_uploading_a_write_on_an_admin_table_then_403_and_nothing_is_written(
    client, token_for, world, table
):
    before = _farm_state(world)
    r = client.post("/v1/sync/upload", json={"ops": [_admin_op(table, world)]}, headers=auth(token_for(world["worker"])))
    assert r.status_code == 403, r.text
    assert _farm_state(world) == before


def test_given_a_worker_when_a_batch_mixes_admin_and_allowed_writes_then_no_admin_write_lands(
    client, token_for, world
):
    before = _farm_state(world)
    ok = op(world["farm"], uuid.uuid4(), kind="put", fields={"title": "t"})
    r = client.post(
        "/v1/sync/upload",
        json={"ops": [_admin_op("worker_parcels", world), ok]},
        headers=auth(token_for(world["worker"])),
    )
    assert r.status_code == 403, r.text
    assert _farm_state(world) == before


@pytest.mark.parametrize("who", ["owner", "manager"])
def test_given_an_owner_or_manager_when_uploading_a_parcel_assignment_then_it_is_applied(
    client, token_for, world, who
):
    r = client.post("/v1/sync/upload", json={"ops": [_admin_op("worker_parcels", world)]}, headers=auth(token_for(world[who])))
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["status"] == "applied"
    assert _assigned(world["farm"], world["worker"]) == {world["parcel"]}


@pytest.mark.parametrize("table", ADMIN_TABLES)
def test_given_a_non_member_when_uploading_an_admin_write_then_404_and_nothing_is_written(
    client, token_for, world, table
):
    before = _farm_state(world)
    r = client.post("/v1/sync/upload", json={"ops": [_admin_op(table, world)]}, headers=auth(token_for(world["stranger"])))
    assert r.status_code == 404, r.text
    assert _farm_state(world) == before


def test_given_a_future_owner_when_creating_their_farm_via_sync_then_it_stays_allowed(client, token_for):
    user, farm = uuid.uuid4(), uuid.uuid4()
    o = op(farm, farm, kind="put", fields={"name": "Ma ferme", "location": {"lat": 33.57, "lon": -7.59}})
    o["table"] = "farms"
    r = client.post("/v1/sync/upload", json={"ops": [o]}, headers=auth(token_for(user)))
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["status"] == "applied"

"""T077 - a deleted farm (Farm.deleted_at) is unreachable: 404 on REST, refused in sync/admin (finding 3)."""
import uuid

import pytest

from tests.helpers import auth, op, sql


@pytest.fixture
def world(make_farm):
    owner, worker = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", worker: "worker"})
    sql("UPDATE farms SET deleted_at = now() WHERE id=$1", farm)
    return dict(owner=owner, worker=worker, farm=farm)


@pytest.mark.parametrize("method,path,body", [
    ("GET", "", None),
    ("PATCH", "", {"name": "Renamed"}),
    ("GET", "/members", None),
    ("GET", "/invitations", None),
    ("POST", "/invitations", {"phone": "+212612345679", "role": "worker"}),
])
def test_given_a_deleted_farm_when_its_owner_calls_a_farm_route_then_404(client, token_for, world, method, path, body):
    r = client.request(method, f"/v1/farms/{world['farm']}{path}", headers=auth(token_for(world["owner"])), json=body)
    assert r.status_code == 404


def test_given_a_deleted_farm_when_a_member_role_is_changed_then_404_and_nothing_changes(client, token_for, world):
    r = client.patch(
        f"/v1/farms/{world['farm']}/members/{world['worker']}",
        headers=auth(token_for(world["owner"])), json={"role": "manager"},
    )
    assert r.status_code == 404
    assert sql("SELECT role FROM farm_members WHERE user_id=$1", world["worker"])[0][0] == "worker"


@pytest.mark.parametrize("table,kind,fields", [
    ("farms", "patch", {"name": "Revived"}),
    ("farms", "delete", {}),
    ("farm_members", "patch", {"user_id": "WORKER", "role": "manager"}),
    ("invitations", "put", {"phone_e164": "+212612345679", "role": "worker"}),
])
def test_given_a_deleted_farm_when_admin_ops_are_uploaded_then_404_and_nothing_is_written(
    client, token_for, world, table, kind, fields,
):
    fields = {k: str(world["worker"]) if v == "WORKER" else v for k, v in fields.items()}
    o = op(world["farm"], uuid.uuid4(), kind=kind, fields=fields)
    o["table"] = table
    r = client.post("/v1/sync/upload", json={"ops": [o]}, headers=auth(token_for(world["owner"])))
    assert r.status_code == 404
    name, role, invites = (
        sql("SELECT name FROM farms WHERE id=$1", world["farm"])[0][0],
        sql("SELECT role FROM farm_members WHERE user_id=$1", world["worker"])[0][0],
        sql("SELECT count(*) FROM invitations")[0][0],
    )
    assert (name, role, invites) == ("Test farm", "worker", 0)


def test_given_a_deleted_farm_when_the_farm_role_is_looked_up_then_there_is_no_role(world):
    import asyncio

    from app.auth.access import farm_role
    from app.db.session import sessionmaker

    async def _run():
        async with sessionmaker() as s:
            return await farm_role(s, world["farm"], world["owner"])

    assert asyncio.run(_run()) is None

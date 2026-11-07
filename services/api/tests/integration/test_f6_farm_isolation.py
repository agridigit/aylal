"""T010 - G1: F6 cross-farm access is a 404 of identical body for every route, never 403."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, call, op_body, routes, world  # noqa: F401


def _scenarios(w):
    return {
        "non_member": (w["owner_b"], w["farm_a"]),
        "unknown_farm": (w["owner"], uuid.uuid4()),
    }


def test_given_a_member_when_using_the_journal_then_the_routes_exist(client, token_for, world):
    w = world
    r = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])))
    assert r.status_code == 200, r.text
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=op_body([w["a1"]]))
    assert r.status_code == 201, r.text


def test_given_a_non_member_or_unknown_farm_when_calling_any_f6_route_then_404_with_an_identical_body(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    assert client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(token_for(w["owner"]))).status_code == 200
    ghost = uuid.uuid4()
    job = uuid.uuid4()  # one stable job id: the reference keys embed it
    reference = {}
    for method, path, body in routes(ghost, oid, w["a1"], job):
        r = call(client, token_for(w["owner"]), method, path, body)
        assert r.status_code == 404
        reference[(method, path.replace(str(ghost), "{farm}"))] = r.text
    for name, (user, farm) in _scenarios(w).items():
        for method, path, body in routes(farm, oid, w["a1"], job):
            r = call(client, token_for(user), method, path, body)
            assert r.status_code == 404, (name, method, path, r.status_code)
            assert r.text == reference[(method, path.replace(str(farm), "{farm}"))], (name, method, path)


def test_given_a_removed_member_when_calling_f6_routes_then_404(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["manager"], w["a1"])
    tok = token_for(w["manager"])
    assert client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(tok)).status_code == 200
    sql("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["manager"])
    for method, path, body in routes(w["farm_a"], oid, w["a1"], uuid.uuid4()):
        assert call(client, tok, method, path, body).status_code == 404, (method, path)


def test_given_a_deleted_farm_when_calling_f6_routes_then_404(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    tok = token_for(w["owner"])
    assert client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(tok)).status_code == 200
    sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    for method, path, body in routes(w["farm_a"], oid, w["a1"], uuid.uuid4()):
        assert call(client, tok, method, path, body).status_code == 404, (method, path)


def test_given_an_operation_of_another_farm_when_loading_it_through_my_farm_then_404(client, token_for, world):
    w = world
    mine = add_operation(w["farm_a"], w["owner"], w["a1"])
    theirs = add_operation(w["farm_b"], w["owner_b"], w["b1"])
    tok = token_for(w["owner"])
    assert client.get(f"/v1/farms/{w['farm_a']}/operations/{mine}", headers=auth(tok)).status_code == 200
    assert client.get(f"/v1/farms/{w['farm_a']}/operations/{theirs}", headers=auth(tok)).status_code == 404
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{theirs}/cancel", headers=auth(tok)).status_code == 404
    assert sql("SELECT status FROM operations WHERE id=$1", theirs)[0][0] == "validated"


def test_given_a_parcel_of_another_farm_when_creating_an_operation_then_it_is_refused_and_nothing_is_written(client, token_for, world):
    w = world
    tok = token_for(w["owner"])
    ok = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(tok), json=op_body([w["a1"]]))
    assert ok.status_code == 201, ok.text
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(tok), json=op_body([w["a1"], w["b1"]]))
    assert r.status_code == 404, r.text
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", w["farm_a"])[0][0] == 1


def test_given_composite_foreign_keys_when_inserting_a_cross_farm_reference_then_the_database_refuses(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    with pytest.raises(Exception, match="foreign key|violates"):
        sql("INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, author_id, type, performed_on, status) "
            "VALUES ($1,$2,$3,$4,$5,'irrigation',$6,'validated')", uuid.uuid4(), w["farm_a"], oid, w["b1"], w["owner"], TODAY)
    with pytest.raises(Exception, match="foreign key|violates"):
        sql("INSERT INTO operation_reminders (id, farm_id, operation_id, fire_on, state) VALUES ($1,$2,$3,$4,'scheduled')",
            uuid.uuid4(), w["farm_b"], oid, TODAY)

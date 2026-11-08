"""T015 - G1: F3 cross-farm access is a 404 with the identical body {"detail":"not_found"} on every route, never 403."""
import uuid

import asyncpg
import pytest

from tests.helpers import auth, sql
from tests.integration._f3 import (  # noqa: F401
    NOT_FOUND,
    add_field,
    call,
    routes,
    seed_alert,
    seed_scene,
    seed_status,
    seed_zone,
    world3,
)


def _objects(w):
    z = seed_zone(w["farm_a"], w["a1"])
    scene, _ = seed_scene(w["farm_a"], w["a1"])
    return seed_alert(w["farm_a"], w["a1"]), z, scene


def _routes_on(farm, w, objs):
    a, z, s = objs
    return routes(farm, w["a1"], a, z, s)


def test_given_a_member_when_reading_the_dashboard_then_it_is_served(client, token_for, world3):
    w = world3
    r = client.get(f"/v1/farms/{w['farm_a']}/dashboard", headers=auth(token_for(w["owner"])))
    assert r.status_code == 200, r.text


def test_given_an_unknown_farm_when_calling_any_f3_route_then_404_not_found_and_the_reference_body_is_exact(client, token_for, world3):
    w = world3
    objs = _objects(w)
    assert client.get(f"/v1/farms/{w['farm_a']}/dashboard", headers=auth(token_for(w["owner"]))).status_code == 200
    for name, method, path, body in _routes_on(uuid.uuid4(), w, objs):
        r = call(client, token_for(w["owner"]), method, path, body)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (name, r.status_code, r.text)


@pytest.mark.parametrize("scenario", ["non_member", "removed_member", "deleted_farm"])
def test_given_no_access_when_calling_any_f3_route_then_404_with_a_body_identical_to_an_unknown_farm(client, token_for, world3, scenario):
    w = world3
    objs = _objects(w)
    tok = token_for(w["manager"] if scenario != "non_member" else w["owner_b"])
    if scenario != "non_member":
        assert client.get(f"/v1/farms/{w['farm_a']}/dashboard", headers=auth(tok)).status_code == 200
    if scenario == "removed_member":
        sql("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["manager"])
    if scenario == "deleted_farm":
        sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    ghost = {n: call(client, tok, m, p, b).text for n, m, p, b in _routes_on(uuid.uuid4(), w, objs)}
    for name, method, path, body in _routes_on(w["farm_a"], w, objs):
        r = call(client, tok, method, path, body)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (scenario, name, r.status_code, r.text)
        assert r.text == ghost[name], (scenario, name)


def test_given_an_object_of_another_farm_when_loaded_through_my_farm_then_404(client, token_for, world3):
    w = world3
    theirs_alert = seed_alert(w["farm_b"], w["b1"])
    theirs_zone = seed_zone(w["farm_b"], w["b1"])
    theirs_scene, _ = seed_scene(w["farm_b"], w["b1"])
    mine = _objects(w)
    tok = token_for(w["owner"])
    assert client.get(f"/v1/farms/{w['farm_a']}/alerts", headers=auth(tok)).status_code == 200
    f = f"/v1/farms/{w['farm_a']}"
    assert client.post(f"{f}/alerts/{theirs_alert}/dismiss", headers=auth(tok)).json() == NOT_FOUND
    assert client.post(f"{f}/zones/{theirs_zone}/dismiss", headers=auth(tok)).json() == NOT_FOUND
    assert client.get(f"{f}/parcels/{w['b1']}/status", headers=auth(tok)).json() == NOT_FOUND
    assert client.get(f"{f}/parcels/{w['b1']}/vigor", headers=auth(tok)).json() == NOT_FOUND
    assert client.get(f"{f}/parcels/{w['a1']}/vigor/scenes/{theirs_scene}/map", headers=auth(tok)).json() == NOT_FOUND
    assert client.post(f"{f}/alerts/{mine[0]}/dismiss", headers=auth(tok)).status_code == 200
    assert sql("SELECT status FROM alerts WHERE id=$1", theirs_alert)[0][0] == "active"


@pytest.mark.parametrize("table,build", [
    ("alerts", lambda w: (("INSERT INTO alerts (id, farm_id, parcel_id, type, severity, source, status, forecast_day, reason_key, reason_params, revision, dedup_key)"
                          " VALUES (gen_random_uuid(),$1,$2,'frost','info','forecast','active',current_date,'k','{}'::jsonb,1,gen_random_uuid()::text)"), (w["farm_a"], w["b1"]))),
    ("parcel_status", lambda w: (("INSERT INTO parcel_status (parcel_id, farm_id, color, reason_key, reason_params, rank, computed_at, data_age_at, imagery_reliability)"
                                 " VALUES (gen_random_uuid(),$1,'green','k','{}'::jsonb,0,now(),now(),'ok')"), (w["farm_a"],))),
])
def test_given_a_composite_foreign_key_when_referencing_a_parcel_of_another_farm_then_the_database_refuses(world3, table, build):
    w = world3
    sql("SELECT 1 FROM " + table + " LIMIT 1")  # the table exists
    q, args = build(w)
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        sql(q, *args)

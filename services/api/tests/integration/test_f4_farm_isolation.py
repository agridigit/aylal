"""T017 - G1: F4 cross-farm access is a 404 with the identical body {"detail":"not_found"} on every route, never 403."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f4 import NOT_FOUND, call, routes, seed_event, seed_plan, world4  # noqa: F401


def _routes_on(farm, w, event):
    return routes(farm, w["a1"], event)


def test_given_a_member_when_reading_advice_then_it_is_served(client, token_for, world4):
    w = world4
    r = client.get(f"/v1/farms/{w['farm_a']}/irrigation/advice", headers=auth(token_for(w["owner"])))
    assert r.status_code == 200, r.text


def test_given_an_unknown_farm_when_calling_any_f4_route_then_404_not_found_with_the_reference_body(client, token_for, world4):
    w = world4
    ev = seed_event(w["farm_a"], w["a1"], w["owner"])
    assert client.get(f"/v1/farms/{w['farm_a']}/irrigation/advice", headers=auth(token_for(w["owner"]))).status_code == 200
    for name, method, path, body in _routes_on(uuid.uuid4(), w, ev):
        r = call(client, token_for(w["owner"]), method, path, body)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (name, r.status_code, r.text)


@pytest.mark.parametrize("scenario", ["non_member", "removed_member", "deleted_farm"])
def test_given_no_access_when_calling_any_f4_route_then_404_with_a_body_identical_to_an_unknown_farm(client, token_for, world4, scenario):
    w = world4
    ev = seed_event(w["farm_a"], w["a1"], w["owner"])
    tok = token_for(w["manager"] if scenario != "non_member" else w["owner_b"])
    if scenario != "non_member":
        assert client.get(f"/v1/farms/{w['farm_a']}/irrigation/advice", headers=auth(tok)).status_code == 200
    if scenario == "removed_member":
        sql("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["manager"])
    if scenario == "deleted_farm":
        sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    ghost = {n: call(client, tok, m, p, b).text for n, m, p, b in _routes_on(uuid.uuid4(), w, ev)}
    for name, method, path, body in _routes_on(w["farm_a"], w, ev):
        r = call(client, tok, method, path, body)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (scenario, name, r.status_code, r.text)
        assert r.text == ghost[name], (scenario, name)


def test_given_an_object_of_another_farm_when_loaded_through_my_farm_then_404_and_nothing_changes(client, token_for, world4):
    w = world4
    theirs = seed_event(w["farm_b"], w["b1"], w["owner_b"])
    tok = token_for(w["owner"])
    f = f"/v1/farms/{w['farm_a']}"
    assert client.get(f"{f}/irrigation/advice", headers=auth(tok)).status_code == 200
    assert client.get(f"{f}/parcels/{w['b1']}/irrigation-system", headers=auth(tok)).json() == NOT_FOUND
    assert client.get(f"{f}/parcels/{w['b1']}/irrigation/advice", headers=auth(tok)).json() == NOT_FOUND
    assert client.get(f"{f}/parcels/{w['b1']}/water-analyses", headers=auth(tok)).json() == NOT_FOUND
    assert client.post(f"{f}/parcels/{w['a1']}/irrigation/events/{theirs}/cancel", headers=auth(tok)).json() == NOT_FOUND
    assert client.post(f"{f}/parcels/{w['b1']}/irrigation/events/{theirs}/cancel", headers=auth(tok)).json() == NOT_FOUND
    assert sql("SELECT status FROM irrigation_events WHERE id=$1", theirs)[0][0] == "done"


@pytest.mark.parametrize("table,cols,args", [
    ("irrigation_systems", "(id, farm_id, parcel_id, kind, sectors_count, pump_flow_m3h)", ("gen_random_uuid()", "$1", "$2", "'drip'", "1", "5")),
    ("irrigation_plans", "(id, farm_id, parcel_id, for_date, kind, confidence, assumptions, computed_at)", ("gen_random_uuid()", "$1", "$2", "current_date", "'no_need'", "'low'", "'[]'::jsonb", "now()")),
    ("water_analyses", "(id, farm_id, parcel_id, ec_ds_m, analysed_on)", ("gen_random_uuid()", "$1", "$2", "1", "current_date")),
])
def test_given_a_composite_foreign_key_when_referencing_a_parcel_of_another_farm_then_the_database_refuses(world4, table, cols, args):
    import asyncpg

    w = world4
    sql("SELECT 1 FROM " + table + " LIMIT 1")  # the table exists
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        sql(f"INSERT INTO {table} {cols} VALUES ({', '.join(args)})", w["farm_a"], w["b1"])


def test_given_the_f4_sql_then_no_read_lacks_the_farm_id_in_its_where_clause():
    import pathlib
    import re

    app = pathlib.Path(__file__).resolve().parents[2] / "app"
    files = sorted((app / "irrigation").glob("*.py")) + [app / "sync" / "irrigation.py"]
    assert any(p.name == "access.py" for p in files)
    stmt = re.compile(r"""(?:"|')\s*SELECT\b[^"']*?\bFROM\s+(irrigation_\w+|water_\w+)\b[^"']*""", re.I | re.S)
    for p in files:
        for m in stmt.finditer(p.read_text(encoding="utf-8")):
            assert re.search(r"farm_id|:farm|visible", m.group(0), re.I), f"{p.name}: {m.group(0)[:120]}"

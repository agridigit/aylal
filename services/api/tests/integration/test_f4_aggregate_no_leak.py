"""T024 - G2: aggregates are computed on the caller's scope only; nothing about invisible parcels leaks."""
import asyncio
import re

from tests.helpers import auth, sql
from tests.integration._f4 import keys_of, seed_event, seed_plan, world4  # noqa: F401

FARM_TOTAL_KEYS = {"farm_total", "total_farm", "farm_area_ha", "total_parcels", "parcel_count", "parcels_total", "area_ha_total"}


def _cons(client, tok, farm):
    return client.get(f"/v1/farms/{farm}/irrigation/consumption", headers=auth(tok))


def _advice(client, tok, farm):
    return client.get(f"/v1/farms/{farm}/irrigation/advice", headers=auth(tok))


def _seed_volumes(w):
    for i, parcel in enumerate(w["p"]):
        seed_event(w["farm_a"], parcel, w["owner"], volume=10.0 * (i + 1), net_mm=1.0)


def test_given_10_parcels_with_3_assigned_when_the_worker_reads_consumption_then_totals_equal_a_manual_sum_on_their_3(client, token_for, world4):
    w = world4
    _seed_volumes(w)
    r = _cons(client, token_for(w["worker"]), w["farm_a"])
    assert r.status_code == 200, r.text
    manual = float(sql("SELECT sum(volume_m3) FROM irrigation_applied WHERE parcel_id = ANY($1)", w["p"][:3])[0][0])
    assert manual == 60.0 and abs(r.json()["total_m3"] - manual) < 1e-6
    assert {p["parcel_id"] for p in r.json()["parcels"]} == {str(p) for p in w["p"][:3]}
    assert str(w["hidden"]) not in r.text


def test_given_the_same_data_then_the_owner_total_covers_the_whole_farm_and_differs(client, token_for, world4):
    w = world4
    _seed_volumes(w)
    owner = _cons(client, token_for(w["owner"]), w["farm_a"]).json()
    assert abs(owner["total_m3"] - 550.0) < 1e-6 and len(owner["parcels"]) == 10


def test_given_a_count_of_parcels_to_irrigate_then_the_worker_count_and_etag_are_a_manual_count_on_their_3(client, token_for, world4):
    w = world4
    r = _advice(client, token_for(w["worker"]), w["farm_a"])
    assert r.status_code == 200
    manual = sql("SELECT count(*) FROM irrigation_plans WHERE parcel_id = ANY($1) AND kind='irrigate'", w["p"][:3])[0][0]
    assert r.json()["to_irrigate_count"] == manual == 3
    assert len(r.json()["items"]) == 3
    assert r.headers["etag"]


def test_given_an_invisible_parcel_changing_then_counts_totals_and_etag_are_invariant_for_the_worker(client, token_for, world4):
    from app.irrigation.cache import bump_data_version

    w = world4
    _seed_volumes(w)
    tok = token_for(w["worker"])
    a1, c1 = _advice(client, tok, w["farm_a"]), _cons(client, tok, w["farm_a"])
    sql("UPDATE irrigation_plans SET kind='no_need', total_minutes=NULL WHERE parcel_id=$1", w["hidden"])
    seed_event(w["farm_a"], w["hidden"], w["owner"], volume=500.0)
    asyncio.run(bump_data_version(w["farm_a"]))
    a2, c2 = _advice(client, tok, w["farm_a"]), _cons(client, tok, w["farm_a"])
    assert a2.json()["to_irrigate_count"] == a1.json()["to_irrigate_count"]
    assert a2.headers["etag"] == a1.headers["etag"]
    assert c2.json()["total_m3"] == c1.json()["total_m3"] and c2.headers.get("etag") == c1.headers.get("etag")


def test_given_the_same_change_then_the_owner_view_does_change(client, token_for, world4):
    from app.irrigation.cache import bump_data_version

    w = world4
    tok = token_for(w["owner"])
    a1 = _advice(client, tok, w["farm_a"])
    sql("UPDATE irrigation_plans SET kind='no_need', total_minutes=NULL WHERE parcel_id=$1", w["hidden"])
    asyncio.run(bump_data_version(w["farm_a"]))
    a2 = _advice(client, tok, w["farm_a"])
    assert a2.json()["to_irrigate_count"] == a1.json()["to_irrigate_count"] - 1 and a2.headers["etag"] != a1.headers["etag"]


def test_given_the_worker_responses_then_no_farm_total_field_and_no_hidden_parcel_exists(client, token_for, world4):
    w = world4
    _seed_volumes(w)
    for r in (_advice(client, token_for(w["worker"]), w["farm_a"]), _cons(client, token_for(w["worker"]), w["farm_a"])):
        assert r.status_code == 200
        assert not (set(keys_of(r.json())) & FARM_TOTAL_KEYS)
        assert str(w["hidden"]) not in r.text


def test_given_a_worker_without_any_parcel_then_everything_is_zero_not_404_and_not_the_farm_total(client, token_for, world4):
    w = world4
    _seed_volumes(w)
    r = _cons(client, token_for(w["worker2"]), w["farm_a"])
    assert r.status_code == 200 and r.json()["total_m3"] == 0 and r.json()["parcels"] == []
    a = _advice(client, token_for(w["worker2"]), w["farm_a"])
    assert a.status_code == 200 and a.json()["items"] == [] and a.json()["to_irrigate_count"] == 0


def test_given_the_aggregate_sources_then_nothing_is_summed_from_farm_area_or_a_shared_cache():
    import pathlib

    app = pathlib.Path(__file__).resolve().parents[2] / "app"
    text = (app / "irrigation" / "consumption.py").read_text(encoding="utf-8")
    assert not re.search(r"farms\.area_ha|SUM\(\s*f\.area_ha", text, re.I)
    assert re.search(r"irrigation_applied", text) and re.search(r"visible_parcels|VISIBLE_PARCELS_SQL", text)
    cache = (app / "irrigation" / "cache.py").read_text(encoding="utf-8")
    assert "advice_cache_key" in cache


def test_given_two_scopes_then_they_never_share_a_cache_entry_and_an_assignment_change_changes_the_key(client, token_for, world4):
    from tests.helpers import sql as q  # noqa: F401
    from tests.integration._f4 import assign

    w = world4
    staff = _advice(client, token_for(w["owner"]), w["farm_a"]).json()
    worker = _advice(client, token_for(w["worker"]), w["farm_a"]).json()
    assert staff["to_irrigate_count"] != worker["to_irrigate_count"]
    before = _advice(client, token_for(w["worker"]), w["farm_a"])
    assign(w["farm_a"], w["worker"], w["p"][3])
    after = _advice(client, token_for(w["worker"]), w["farm_a"])
    assert len(after.json()["items"]) == 4 and after.headers["etag"] != before.headers["etag"]

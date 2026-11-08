"""T020 - G2: aggregates are computed on the caller's scope only; nothing about invisible parcels leaks."""
import asyncio

from tests.helpers import auth, sql
from tests.integration._f3 import keys_of, set_status, world3  # noqa: F401

FARM_TOTAL_KEYS = {"area_ha", "total", "total_parcels", "parcel_count", "parcels_total", "farm_area_ha", "farm_total"}


def _dash(client, tok, farm):
    return client.get(f"/v1/farms/{farm}/dashboard", headers=auth(tok))


def _summary(client, tok, farm):
    return client.get(f"/v1/farms/{farm}/summary/today", headers=auth(tok))


def test_given_10_parcels_with_3_assigned_when_the_worker_reads_then_counts_equal_a_manual_count_on_their_parcels(client, token_for, world3):
    w = world3
    r = _dash(client, token_for(w["worker"]), w["farm_a"])
    assert r.status_code == 200, r.text
    manual = {c: sql("SELECT count(*) FROM parcel_status WHERE parcel_id = ANY($1) AND color=$2", w["p"][:3], c)[0][0] for c in ("red", "orange", "green")}
    assert r.json()["counts"] == manual == {"red": 1, "orange": 1, "green": 1}
    assert len(r.json()["parcels"]) == 3


def test_given_an_invisible_parcel_changing_state_then_counts_etag_order_summary_are_invariant_for_the_worker(client, token_for, world3):
    w = world3
    tok = token_for(w["worker"])
    d1, s1 = _dash(client, tok, w["farm_a"]), _summary(client, tok, w["farm_a"])
    assert d1.status_code == 200 and s1.status_code == 200
    set_status(w["hidden"], "green")                  # the invisible red turns green
    set_status(w["p"][7], "red")                      # another invisible parcel turns red
    from app.monitoring.cache import bump_data_version

    asyncio.run(bump_data_version(w["farm_a"]))
    d2, s2 = _dash(client, tok, w["farm_a"]), _summary(client, tok, w["farm_a"])
    assert d2.json()["counts"] == d1.json()["counts"]
    assert [p["parcel_id"] for p in d2.json()["parcels"]] == [p["parcel_id"] for p in d1.json()["parcels"]]
    assert d2.headers["etag"] == d1.headers["etag"]
    assert s2.json()["items"] == s1.json()["items"]


def test_given_the_same_change_then_the_owner_view_does_change(client, token_for, world3):
    w = world3
    tok = token_for(w["owner"])
    d1 = _dash(client, tok, w["farm_a"])
    assert d1.json()["counts"] == {"red": 2, "orange": 2, "green": 6}
    set_status(w["hidden"], "green")
    from app.monitoring.cache import bump_data_version

    asyncio.run(bump_data_version(w["farm_a"]))
    d2 = _dash(client, tok, w["farm_a"])
    assert d2.json()["counts"] == {"red": 1, "orange": 2, "green": 7} and d2.headers["etag"] != d1.headers["etag"]


def test_given_the_worker_response_then_no_farm_total_field_exists(client, token_for, world3):
    w = world3
    for r in (_dash(client, token_for(w["worker"]), w["farm_a"]), _summary(client, token_for(w["worker"]), w["farm_a"])):
        assert r.status_code == 200
        assert not (set(keys_of(r.json())) & FARM_TOTAL_KEYS)
        assert str(w["hidden"]) not in r.text


def test_given_a_worker_without_any_parcel_then_everything_is_zero_not_404_and_not_the_farm_total(client, token_for, world3):
    w = world3
    r = _dash(client, token_for(w["worker2"]), w["farm_a"])
    assert r.status_code == 200 and r.json()["counts"] == {"red": 0, "orange": 0, "green": 0} and r.json()["parcels"] == []
    s = _summary(client, token_for(w["worker2"]), w["farm_a"])
    assert s.status_code == 200 and s.json()["items"] == []


def test_given_two_scopes_then_they_never_share_a_cache_entry(client, token_for, world3):
    w = world3
    staff = _dash(client, token_for(w["owner"]), w["farm_a"]).json()
    worker = _dash(client, token_for(w["worker"]), w["farm_a"]).json()
    again = _dash(client, token_for(w["owner"]), w["farm_a"]).json()
    assert staff["counts"] != worker["counts"] and again["counts"] == staff["counts"]
    assert _dash(client, token_for(w["worker"]), w["farm_a"]).json()["counts"] == worker["counts"]


def test_given_a_data_version_bump_then_the_cached_view_is_invalidated(client, token_for, world3):
    from app.monitoring.cache import bump_data_version

    w = world3
    tok = token_for(w["worker"])
    assert _dash(client, tok, w["farm_a"]).json()["counts"]["green"] == 1
    set_status(w["p"][0], "green")
    assert _dash(client, tok, w["farm_a"]).status_code == 200
    asyncio.run(bump_data_version(w["farm_a"]))
    assert _dash(client, tok, w["farm_a"]).json()["counts"] == {"red": 0, "orange": 1, "green": 2}

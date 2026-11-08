"""T070 (US4) - R4-A1..A3: the consumption aggregate on the real stack of components: m3 and m3/ha per parcel and for the season, all
sources of water, window <= 24 months, cursor, scope of the caller (worker: assigned parcels only, archived parcels excluded for all)."""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import NOT_FOUND, YESTERDAY4, call, seed_event, seed_season, world4  # noqa: F401


def _get(client, token_for, w, who, query=""):
    return call(client, token_for(w[who]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/consumption{query}")


def _area(parcel):
    return float(sql("SELECT COALESCE(area_calc_ha, area_declared_ha, ST_Area(geometry::geography)/10000.0) FROM parcels WHERE id=$1", parcel)[0][0])


def _by_parcel(body):
    return {p["parcel_id"]: p for p in body["parcels"]}


def test_given_irrigations_when_opening_the_follow_up_then_the_volume_and_the_volume_per_hectare_are_given_for_the_season(client, token_for, world4):
    w = world4
    season = seed_season(w["farm_a"], w["a1"])
    seed_event(w["farm_a"], w["a1"], w["owner"], volume=30.0, season=season)
    seed_event(w["farm_a"], w["a1"], w["owner"], volume=12.5, season=season)
    body = _get(client, token_for, w, "owner", f"?season_id={season}").json()
    row = _by_parcel(body)[str(w["a1"])]
    assert row["volume_m3"] == 42.5 and abs(row["volume_m3_per_ha"] - 42.5 / _area(w["a1"])) < 1e-6 and body["season_id"] == str(season)


def test_given_several_parcels_then_each_one_shows_its_own_volume_and_its_ratio(client, token_for, world4):
    w = world4
    seed_event(w["farm_a"], w["p"][0], w["owner"], volume=10.0)
    seed_event(w["farm_a"], w["p"][1], w["owner"], volume=40.0)
    sql("UPDATE parcels SET area_declared_ha=4, area_calc_ha=4 WHERE id=$1", w["p"][1])
    rows = _by_parcel(_get(client, token_for, w, "owner").json())
    assert rows[str(w["p"][1])]["volume_m3_per_ha"] == 10.0 and rows[str(w["p"][0])]["volume_m3"] == 10.0


def test_given_a_season_without_irrigation_then_the_totals_are_zero_so_the_client_shows_the_empty_state(client, token_for, world4):
    w = world4
    body = _get(client, token_for, w, "owner").json()
    assert body["total_m3"] == 0 and all(p["volume_m3"] == 0 and p["events"] == 0 for p in body["parcels"])


def test_given_other_sources_of_applied_water_then_they_are_counted_and_cancelled_events_are_not(client, token_for, world4):
    w = world4
    done = seed_event(w["farm_a"], w["a1"], w["owner"], volume=20.0)
    cancelled = seed_event(w["farm_a"], w["a1"], w["owner"], volume=99.0, status="cancelled")
    sql("INSERT INTO irrigation_applied (id, farm_id, parcel_id, performed_on, volume_m3, net_mm) VALUES (gen_random_uuid(),$1,$2,$3,5,1)", w["farm_a"], w["a1"], YESTERDAY4)
    row = _by_parcel(_get(client, token_for, w, "owner").json())[str(w["a1"])]
    assert row["volume_m3"] == 25.0 and row["events"] == 2


def test_given_a_worker_then_the_totals_are_the_sum_of_their_assigned_parcels_and_never_the_farm_total(client, token_for, world4):
    w = world4
    for i, p in enumerate(w["p"]):
        seed_event(w["farm_a"], p, w["owner"], volume=10.0 * (i + 1))
    worker = _get(client, token_for, w, "worker").json()
    assert {p["parcel_id"] for p in worker["parcels"]} == {str(p) for p in w["p"][:3]} and worker["total_m3"] == 60.0
    assert _get(client, token_for, w, "owner").json()["total_m3"] == 550.0
    assert str(w["hidden"]) not in str(worker)


def test_given_an_archived_parcel_then_it_leaves_the_totals_of_every_role(client, token_for, world4):
    w = world4
    seed_event(w["farm_a"], w["p"][1], w["owner"], volume=100.0)
    before = _get(client, token_for, w, "owner").json()["total_m3"]
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["p"][1])
    for who in ("owner", "manager", "worker"):
        body = _get(client, token_for, w, who).json()
        assert str(w["p"][1]) not in {p["parcel_id"] for p in body["parcels"]}
    assert _get(client, token_for, w, "owner").json()["total_m3"] == before - 100.0


@pytest.mark.parametrize("query,status", [
    ("?from=2024-06-04&to=2026-06-04", 200), ("?from=2024-06-03&to=2026-06-04", 422), ("?from=2026-06-05&to=2026-06-04", 422), ("?limit=101", 422), ("?limit=100", 200),
])
def test_given_a_window_or_a_limit_then_more_than_24_months_or_100_items_is_refused_before_any_read(client, token_for, world4, query, status):
    assert _get(client, token_for, world4, "owner", query).status_code == status


def test_given_more_parcels_than_the_page_then_a_cursor_leads_to_the_rest_without_overlap(client, token_for, world4):
    w = world4
    first = _get(client, token_for, w, "owner", "?limit=4").json()
    assert len(first["parcels"]) == 4 and first["next_cursor"]
    second = _get(client, token_for, w, "owner", f"?limit=4&cursor={first['next_cursor']}").json()
    assert not {p["parcel_id"] for p in first["parcels"]} & {p["parcel_id"] for p in second["parcels"]}


def test_given_the_same_scope_then_a_conditional_read_is_a_304_and_the_etag_differs_between_scopes(client, token_for, world4):
    w = world4
    seed_event(w["farm_a"], w["a1"], w["owner"])
    owner = _get(client, token_for, w, "owner")
    worker = _get(client, token_for, w, "worker")
    assert owner.headers["etag"] != worker.headers["etag"]
    again = client.get(f"/v1/farms/{w['farm_a']}/irrigation/consumption", headers={**{"Authorization": f"Bearer {token_for(w['owner'])}"}, "If-None-Match": owner.headers["etag"]})
    assert again.status_code == 304


def test_given_another_farm_or_a_non_member_then_the_answer_is_the_same_404(client, token_for, world4):
    w = world4
    other = call(client, token_for(w["owner_b"]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/consumption")
    outsider = call(client, token_for(w["outsider"]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/consumption")
    unknown = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{uuid.uuid4()}/irrigation/consumption")
    assert {(r.status_code, str(r.json())) for r in (other, outsider, unknown)} == {(404, str(NOT_FOUND))}

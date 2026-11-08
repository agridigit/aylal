"""T075 - R6-A1, R6-A2: the previous campaign is read on the caller's scope and aligned by day of campaign (season start, else 1 September);
at most 200 points per curve; no reference means an explicit absence, never an invented curve."""
import datetime as dt

from tests.helpers import auth
from tests.integration._f3 import call, seed_season_at, seed_vigor_points, world3  # noqa: F401

TODAY = dt.date.today()
D = dt.timedelta


def _year_before(d):
    return d.replace(year=d.year - 1, day=28) if (d.month, d.day) == (2, 29) else d.replace(year=d.year - 1)


def _compare(client, token_for, w, parcel=None, who="owner"):
    return call(client, token_for(w[who]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel or w['a1']}/vigor/compare")


def test_given_a_season_started_off_september_when_comparing_then_both_curves_count_days_from_that_season_start(client, token_for, world3):
    w = world3
    p = w["p"][8]
    start = TODAY - D(days=100)
    seed_season_at(w["farm_a"], p, start)
    seed_vigor_points(w["farm_a"], p, [start + D(days=10), start + D(days=40)])
    seed_vigor_points(w["farm_a"], p, [_year_before(start) + D(days=10), _year_before(start) + D(days=40)])
    b = _compare(client, token_for, w, p).json()
    assert b["reference_available"] is True
    assert [x["day_of_campaign"] for x in b["current"]] == [10, 40]
    assert [x["day_of_campaign"] for x in b["previous"]] == [10, 40]


def test_given_no_season_when_comparing_then_the_campaign_starts_on_the_last_1_september(client, token_for, world3):
    w = world3
    p = w["p"][8]
    start = dt.date(TODAY.year if TODAY >= dt.date(TODAY.year, 9, 1) else TODAY.year - 1, 9, 1)
    seed_vigor_points(w["farm_a"], p, [start + D(days=3)])
    seed_vigor_points(w["farm_a"], p, [start.replace(year=start.year - 1) + D(days=3)])
    b = _compare(client, token_for, w, p).json()
    assert [x["day_of_campaign"] for x in b["current"]] == [3] and [x["day_of_campaign"] for x in b["previous"]] == [3]


def test_given_a_dense_history_when_comparing_then_each_curve_has_at_most_200_points_in_date_order(client, token_for, world3):
    w = world3
    p = w["p"][8]
    start = TODAY - D(days=300)
    seed_season_at(w["farm_a"], p, start)
    seed_vigor_points(w["farm_a"], p, [start + D(days=i) for i in range(300)])
    seed_vigor_points(w["farm_a"], p, [_year_before(start) + D(days=i) for i in range(300)])
    b = _compare(client, token_for, w, p).json()
    for k in ("current", "previous"):
        days = [x["acquired_on"] for x in b[k]]
        assert 0 < len(days) <= 200 and days == sorted(days) and len(set(days)) == len(days)


def test_given_a_parcel_without_last_year_history_when_comparing_then_the_reference_is_absent_and_the_current_curve_is_still_served(client, token_for, world3):
    w = world3
    p = w["p"][8]
    seed_vigor_points(w["farm_a"], p, [TODAY - D(days=5)])
    b = _compare(client, token_for, w, p).json()
    assert b["reference_available"] is False and not b["previous"] and len(b["current"]) == 1


def test_given_last_year_points_all_under_80_percent_clear_when_comparing_then_there_is_no_reference(client, token_for, world3):
    w = world3
    p = w["p"][8]
    start = TODAY - D(days=60)
    seed_season_at(w["farm_a"], p, start)
    seed_vigor_points(w["farm_a"], p, [start + D(days=5)])
    seed_vigor_points(w["farm_a"], p, [_year_before(start) + D(days=5)], clear=60)
    b = _compare(client, token_for, w, p).json()
    assert b["reference_available"] is False and not b["previous"]


def test_given_only_recent_history_under_12_months_when_comparing_then_there_is_no_reference(client, token_for, world3):
    w = world3
    p = w["p"][8]
    seed_vigor_points(w["farm_a"], p, [TODAY - D(days=i) for i in (3, 90, 200)])
    assert _compare(client, token_for, w, p).json()["reference_available"] is False


def test_given_points_of_another_parcel_of_the_farm_when_comparing_then_none_of_them_is_served(client, token_for, world3):
    w = world3
    seed_vigor_points(w["farm_a"], w["hidden"], [TODAY - D(days=4)])
    b = _compare(client, token_for, w, w["p"][8]).json()
    assert b["current"] == [] and b["previous"] == []


def test_given_a_worker_when_comparing_an_unassigned_parcel_then_404_identical_to_an_unknown_parcel(client, token_for, world3):
    w = world3
    seed_vigor_points(w["farm_a"], w["hidden"], [TODAY - D(days=4)])
    hidden = _compare(client, token_for, w, w["hidden"], who="worker")
    unknown = _compare(client, token_for, w, "00000000-0000-4000-8000-000000000000", who="worker")
    assert hidden.status_code == 404 and hidden.json() == unknown.json() == {"detail": "not_found"}


def test_given_a_worker_when_comparing_an_assigned_parcel_then_the_comparison_is_served(client, token_for, world3):
    w = world3
    assert _compare(client, token_for, w, w["a1"], who="worker").status_code == 200


def test_given_another_farm_or_an_outsider_when_comparing_then_404_without_any_point(client, token_for, world3):
    w = world3
    seed_vigor_points(w["farm_a"], w["a1"], [TODAY - D(days=4)])
    cross = client.get(f"/v1/farms/{w['farm_b']}/parcels/{w['a1']}/vigor/compare", headers=auth(token_for(w["owner_b"])))
    foreign = _compare(client, token_for, w, w["a1"], who="owner_b")
    outsider = _compare(client, token_for, w, w["a1"], who="outsider")
    for r in (cross, foreign, outsider):
        assert r.status_code == 404 and r.json() == {"detail": "not_found"}


def test_given_an_archived_parcel_when_a_worker_compares_then_404(client, token_for, world3):
    from tests.helpers import sql

    w = world3
    sql("UPDATE parcels SET archived_at = now() WHERE id = $1", w["a1"])
    assert _compare(client, token_for, w, w["a1"], who="worker").status_code == 404

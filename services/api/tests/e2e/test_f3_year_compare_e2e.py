"""T076 - R6-A1, R6-A2 on the running stack: two campaigns aligned on the season start, absence of reference, worker scope."""
import datetime as dt
import uuid

from tests.e2e._f3 import client, seed_crop_stage, setup_farm
from tests.integration._f3 import seed_vigor_points

TODAY = dt.date.today()
D = dt.timedelta


def test_given_two_campaigns_when_the_owner_compares_then_the_curves_are_aligned_on_the_season_start():
    with client() as c:
        s = setup_farm(c, 1)
        farm, parcel = uuid.UUID(s["farm"]), uuid.UUID(s["parcels"][0])
        seed_crop_stage(s["farm"], s["parcels"][0], frost_c=-2)  # active season started 90 days ago
        start = TODAY - D(days=90)
        seed_vigor_points(farm, parcel, [start + D(days=12), start + D(days=30)])
        seed_vigor_points(farm, parcel, [start.replace(year=start.year - 1) + D(days=12), start.replace(year=start.year - 1) + D(days=30)])
        b = c.get(f"/farms/{s['farm']}/parcels/{parcel}/vigor/compare", headers=s["oh"]).json()
        assert b["reference_available"] is True
        assert [p["day_of_campaign"] for p in b["current"]] == [12, 30] == [p["day_of_campaign"] for p in b["previous"]]


def test_given_a_new_parcel_when_the_owner_compares_then_the_absence_of_reference_is_explicit_and_nothing_is_invented():
    with client() as c:
        s = setup_farm(c, 1)
        r = c.get(f"/farms/{s['farm']}/parcels/{s['parcels'][0]}/vigor/compare", headers=s["oh"])
        assert r.status_code == 200
        assert r.json() == {"reference_available": False, "current": [], "previous": []}


def test_given_a_worker_when_comparing_a_hidden_parcel_then_404_and_an_assigned_one_200():
    with client() as c:
        s = setup_farm(c, 2, worker=True, hidden=1)
        visible, hidden = s["parcels"]
        assert c.get(f"/farms/{s['farm']}/parcels/{visible}/vigor/compare", headers=s["wh"]).status_code == 200
        r = c.get(f"/farms/{s['farm']}/parcels/{hidden}/vigor/compare", headers=s["wh"])
        assert r.status_code == 404 and r.json() == {"detail": "not_found"}

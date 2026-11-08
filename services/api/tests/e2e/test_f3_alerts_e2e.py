"""T050 - R2-A1..A4 on the running stack with the real worker: frost at 48 h on a sensitive stage notifies the evening before before 18:00; no alert when the threshold is not reached.

One farm and one worker login for the whole file (the OTP limiter is per IP); each test reads only the alerts of its own parcel.
"""
import datetime as dt
import uuid

import pytest

from tests.e2e._f3 import TODAY, client, day, run_job, seed_crop_stage, seed_forecast, setup_farm

MOROCCO = dt.timezone(dt.timedelta(hours=1))


@pytest.fixture(scope="module")
def farm():
    with client() as c:
        yield setup_farm(c, 4, worker=True, hidden=3)


def _alerts(c, s, who="oh"):
    return c.get(f"/farms/{s['farm']}/alerts", headers=s[who]).json()


def test_given_a_frost_forecast_at_48_hours_on_a_sensitive_crop_when_the_worker_evaluates_then_the_alert_is_served_and_due_before_18h_the_evening_before(farm):
    s = farm
    sensitive, dormant = s["parcels"][0], s["parcels"][1]
    slug = seed_crop_stage(s["farm"], sensitive, frost_c=-2)
    seed_crop_stage(s["farm"], dormant, frost_c=None)
    seed_forecast(s["farm"], [day(2, tmin=-5)])
    run_job("evaluate_alerts", farm_id=uuid.UUID(s["farm"]))
    with client() as c:
        frost = [a for a in _alerts(c, s) if a["type"] == "frost"]
        assert [a["parcel_id"] for a in frost] == [sensitive]
        assert frost[0]["crop_slug"] == slug and frost[0]["severity"] == "critical" and frost[0]["reason_key"] and frost[0]["source"] and frost[0]["status"] == "active"
        due = dt.datetime.fromisoformat(frost[0]["notify_at"]).astimezone(MOROCCO)
        assert due.date() == TODAY + dt.timedelta(days=1) and due.hour < 18
        assert {a["parcel_id"] for a in _alerts(c, s, "wh")} == {sensitive}


def test_given_a_strong_wind_forecast_when_the_worker_evaluates_then_the_alert_advises_not_to_spray(farm):
    s = farm
    p = s["parcels"][2]
    seed_crop_stage(s["farm"], p, frost_c=-2)
    seed_forecast(s["farm"], [day(1, wind_kmh=48)])
    run_job("evaluate_alerts", farm_id=uuid.UUID(s["farm"]))
    with client() as c:
        wind = [a for a in _alerts(c, s) if a["type"] == "strong_wind" and a["parcel_id"] == p]
        assert wind and wind[0]["advice_key"] == "do_not_spray"


def test_given_a_frost_that_does_not_reach_the_stage_threshold_when_the_worker_evaluates_then_no_frost_alert_is_served_for_that_parcel(farm):
    s = farm
    p = s["parcels"][3]
    seed_crop_stage(s["farm"], p, frost_c=-8)
    seed_forecast(s["farm"], [day(2, tmin=-3)])
    run_job("evaluate_alerts", farm_id=uuid.UUID(s["farm"]))
    with client() as c:
        assert [a for a in _alerts(c, s) if a["type"] == "frost" and a["parcel_id"] == p] == []


def test_given_an_alert_when_a_worker_tries_to_dismiss_it_then_403_and_the_owner_dismisses_it(farm):
    s = farm
    seed_forecast(s["farm"], [day(2, tmin=-5)])
    run_job("evaluate_alerts", farm_id=uuid.UUID(s["farm"]))
    with client() as c:
        alert = next(a["id"] for a in _alerts(c, s) if a["parcel_id"] == s["parcels"][0] and a["type"] == "frost")
        assert c.post(f"/farms/{s['farm']}/alerts/{alert}/dismiss", headers=s["wh"]).status_code == 403
        assert c.post(f"/farms/{s['farm']}/alerts/{alert}/dismiss", headers=s["oh"]).json()["status"] == "dismissed"

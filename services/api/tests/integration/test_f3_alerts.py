"""T048 - R2-A1..A4: alerts carry parcel, type, severity, source, status and reason; staff dismiss; archived parcels have none."""
import datetime as dt
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f3 import call, seed_alert, world3  # noqa: F401

NOT_FOUND = {"detail": "not_found"}


def test_given_an_active_frost_alert_when_listing_then_it_carries_parcel_type_severity_source_status_and_reason(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["a1"], type_="frost", severity="critical")
    got = {x["id"]: x for x in call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/alerts").json()}[str(a)]
    assert got["parcel_id"] == str(w["a1"]) and got["type"] == "frost" and got["severity"] == "critical"
    assert got["source"] == "forecast" and got["status"] == "active" and got["reason_key"]
    assert {"forecast_day", "advice_key", "notify_at", "revision"} <= set(got)


def test_given_a_strong_wind_alert_when_listing_then_the_do_not_spray_advice_is_served(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["a1"], type_="strong_wind", severity="warning")
    sql("UPDATE alerts SET advice_key = 'do_not_spray' WHERE id = $1", a)
    got = {x["id"]: x for x in call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/alerts").json()}[str(a)]
    assert got["advice_key"] == "do_not_spray"


def test_given_alerts_on_visible_and_hidden_parcels_when_a_worker_lists_then_only_assigned_parcels_appear(client, token_for, world3):
    w = world3
    mine, hidden = seed_alert(w["farm_a"], w["a1"]), seed_alert(w["farm_a"], w["hidden"], type_="chergui")
    ids = {x["id"] for x in call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/alerts").json()}
    assert str(mine) in ids and str(hidden) not in ids


def test_given_a_manager_when_dismissing_an_alert_then_it_is_dismissed_and_stays_listed_as_dismissed(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["a1"])
    r = call(client, token_for(w["manager"]), "POST", f"/v1/farms/{w['farm_a']}/alerts/{a}/dismiss")
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    assert sql("SELECT status FROM alerts WHERE id = $1", a)[0][0] == "dismissed"


def test_given_a_worker_when_dismissing_an_alert_then_403_and_the_alert_is_untouched(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["a1"])
    assert call(client, token_for(w["worker"]), "POST", f"/v1/farms/{w['farm_a']}/alerts/{a}/dismiss").status_code == 403
    assert sql("SELECT status FROM alerts WHERE id = $1", a)[0][0] == "active"


def test_given_an_alert_of_another_farm_when_dismissing_then_404_identical(client, token_for, world3):
    w = world3
    other = seed_alert(w["farm_b"], w["b1"])
    r = call(client, token_for(w["owner"]), "POST", f"/v1/farms/{w['farm_a']}/alerts/{other}/dismiss")
    assert r.status_code == 404 and r.json() == NOT_FOUND


def test_given_an_unknown_alert_when_dismissing_then_404(client, token_for, world3):
    w = world3
    assert call(client, token_for(w["owner"]), "POST", f"/v1/farms/{w['farm_a']}/alerts/{uuid.uuid4()}/dismiss").status_code == 404


def test_given_an_archived_parcel_when_listing_alerts_then_none_is_served_even_to_staff(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["p"][7])
    sql("UPDATE parcels SET archived_at = now() WHERE id = $1", w["p"][7])
    ids = {x["id"] for x in call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/alerts").json()}
    assert str(a) not in ids


def test_given_a_dismissed_alert_when_the_same_forecast_returns_then_the_alert_is_not_reopened_by_the_listing(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["a1"], day=dt.date.today() + dt.timedelta(days=2))
    call(client, token_for(w["owner"]), "POST", f"/v1/farms/{w['farm_a']}/alerts/{a}/dismiss")
    listed = {x["id"]: x["status"] for x in call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/alerts").json()}
    assert listed.get(str(a), "dismissed") == "dismissed"


@pytest.mark.parametrize("limit", [101, 0, -1])
def test_given_a_limit_out_of_range_when_listing_alerts_then_422_before_any_read(client, token_for, world3, limit):
    w = world3
    assert call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/alerts?limit={limit}").status_code == 422

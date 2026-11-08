"""T080 - R7-A1, R7-A2: the summary is computed on the caller's scope, in the caller's language; the weather of the day is never invented;
the notification settings are the caller's own."""
import datetime as dt
import json
import uuid

from tests.helpers import auth, sql
from tests.integration._f3 import call, set_status, world3  # noqa: F401

TODAY = dt.date.today()


def _today(client, token_for, w, who="owner", farm=None):
    return call(client, token_for(w[who]), "GET", f"/v1/farms/{farm or w['farm_a']}/summary/today")


def _put(client, token_for, w, body, who="owner", farm=None):
    return client.put(f"/v1/farms/{farm or w['farm_a']}/summary/settings", headers=auth(token_for(w[who])), json=body)


def _weather(farm, **over):
    day = {"date": TODAY.isoformat(), "tmin": 8.0, "tmax": 22.0, "rain_mm": 0.0, "wind_kmh": 8.0, "humidity_pct": 60.0, **over}
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,'33.6:-7.6',now(),'ok',$2::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET days = EXCLUDED.days, fetched_at = now(), availability = 'ok'", farm, json.dumps([day]))


def test_given_red_orange_and_green_parcels_when_reading_then_only_red_then_orange_are_listed_in_that_order(client, token_for, world3):
    w = world3
    items = _today(client, token_for, w).json()["items"]
    assert [i["color"] for i in items] == sorted((i["color"] for i in items), key=lambda c: c != "red")
    assert {i["color"] for i in items} <= {"red", "orange"} and items


def test_given_a_user_language_when_reading_then_the_summary_is_in_that_language_and_unknown_falls_back_to_french(client, token_for, world3):
    w = world3
    for lang, expected in (("ary", "ary"), ("ar", "ar"), ("fr", "fr"), (None, "fr")):
        sql("UPDATE users SET language = $2 WHERE id = $1", w["owner"], lang)
        assert _today(client, token_for, w).json()["locale"] == expected


def test_given_a_worker_when_reading_then_no_invisible_parcel_appears_anywhere_in_the_body(client, token_for, world3):
    w = world3
    r = _today(client, token_for, w, "worker")
    assert str(w["hidden"]) not in r.text
    assert {i["parcel_id"] for i in r.json()["items"]} <= {str(p) for p in w["p"][:3]}


def test_given_a_stored_forecast_without_any_icon_when_reading_then_the_weather_code_is_null_never_the_text_none(client, token_for, world3):
    w = world3
    _weather(w["farm_a"])
    assert _today(client, token_for, w).json()["weather_code"] is None


def test_given_a_stored_forecast_when_reading_then_the_weather_code_is_the_icon_of_the_day(client, token_for, world3):
    w = world3
    _weather(w["farm_a"], icon="rain")
    assert _today(client, token_for, w).json()["weather_code"] == "rain"


def test_given_no_forecast_when_reading_then_the_weather_code_is_null(client, token_for, world3):
    w = world3
    assert _today(client, token_for, w).json()["weather_code"] is None


def test_given_a_parcel_turning_green_when_reading_again_then_it_leaves_the_summary(client, token_for, world3):
    w = world3
    first = {i["parcel_id"] for i in _today(client, token_for, w).json()["items"]}
    set_status(w["p"][0], "green")
    assert str(w["p"][0]) in first
    assert str(w["p"][0]) not in {i["parcel_id"] for i in _today(client, token_for, w).json()["items"]}


def test_given_a_valid_hour_when_saving_then_it_is_stored_for_the_caller_only(client, token_for, world3):
    w = world3
    assert _put(client, token_for, w, {"summary_hour": 18, "alerts_enabled": False}).json() == {"summary_hour": 18, "alerts_enabled": False}
    assert _put(client, token_for, w, {"summary_hour": 5, "alerts_enabled": True}, who="worker").status_code == 200
    rows = {r["user_id"]: (r["summary_hour"], r["alerts_enabled"]) for r in sql("SELECT user_id, summary_hour, alerts_enabled FROM notification_prefs WHERE farm_id = $1", w["farm_a"])}
    assert rows == {w["owner"]: (18, False), w["worker"]: (5, True)}


def test_given_an_hour_out_of_range_or_not_an_integer_when_saving_then_422_and_nothing_is_stored(client, token_for, world3):
    w = world3
    for bad in (24, -1, 7.5, None):
        assert _put(client, token_for, w, {"summary_hour": bad, "alerts_enabled": True}).status_code == 422, bad
    assert sql("SELECT count(*) FROM notification_prefs WHERE farm_id = $1", w["farm_a"])[0][0] == 0


def test_given_a_non_member_or_another_farm_when_saving_or_reading_then_404_identical(client, token_for, world3):
    w = world3
    for who in ("outsider", "owner_b"):
        assert _put(client, token_for, w, {"summary_hour": 7, "alerts_enabled": True}, who=who).json() == {"detail": "not_found"}
        assert _today(client, token_for, w, who).json() == {"detail": "not_found"}
    assert sql("SELECT count(*) FROM notification_prefs WHERE farm_id = $1", w["farm_a"])[0][0] == 0


def test_given_a_removed_member_when_reading_then_404_and_a_deleted_farm_gives_404_too(client, token_for, world3):
    w = world3
    sql("UPDATE farm_members SET removed_at = now() WHERE farm_id = $1 AND user_id = $2", w["farm_a"], w["worker2"])
    assert _today(client, token_for, w, "worker2").status_code == 404
    sql("UPDATE farms SET deleted_at = now() WHERE id = $1", w["farm_a"])
    assert _today(client, token_for, w, "owner").status_code == 404
    assert uuid.UUID(str(w["farm_a"]))

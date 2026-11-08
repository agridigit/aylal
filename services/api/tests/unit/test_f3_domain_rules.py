"""T014 - F3 shared domain rules: Python mirrors the TS vectors (thresholds are fixtures only)."""
import datetime as dt
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _vec(name):
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))


ALERTS, STATUS, ANOMALY = _vec("f3_alert_rules.json"), _vec("f3_parcel_status.json"), _vec("f3_anomaly.json")
CLOUD, RELIABILITY, NOTIFY = _vec("f3_cloud_rule.json"), _vec("f3_reliability.json"), _vec("f3_notify_schedule.json")


@pytest.mark.parametrize("l", ALERTS["lookups"], ids=lambda l: f"{l['crop_slug']}/{l['stage_key']}")
def test_given_a_crop_and_stage_when_looking_up_thresholds_then_found_matches(l):
    from app.domain.weather_thresholds import thresholds_for

    assert (thresholds_for(ALERTS["thresholds"], l["crop_slug"], l["stage_key"]) is not None) is l["found"]


@pytest.mark.parametrize("c", ALERTS["evaluations"], ids=lambda c: c["name"])
def test_given_a_forecast_day_when_evaluating_then_alerts_match(c):
    from app.domain.alert_rules import evaluate_day
    from app.domain.weather_thresholds import thresholds_for

    out = evaluate_day(thresholds_for(ALERTS["thresholds"], c["crop_slug"], c["stage_key"]), c["day"])
    assert sorted(a["type"] for a in out) == sorted(e["type"] for e in c["expected"])
    for e in c["expected"]:
        got = next(a for a in out if a["type"] == e["type"])
        if "severity" in e:
            assert got["severity"] == e["severity"]
        if "advice_key" in e:
            assert got["advice_key"] == e["advice_key"]


def test_given_no_thresholds_then_no_alert_is_produced():
    from app.domain.alert_rules import evaluate_day

    assert evaluate_day(None, {"date": "2026-12-05", "tmin": -9, "tmax": 50, "rain_mm": 99, "wind_kmh": 99, "humidity_pct": 1}) == []


def test_given_any_component_changing_then_the_dedup_key_changes_and_is_stable():
    from app.domain.alert_rules import dedup_key

    b = ALERTS["dedup"]["base"]
    keys = {dedup_key(**b)} | {dedup_key(**{**b, **v}) for v in ALERTS["dedup"]["variants"]}
    assert len(keys) == len(ALERTS["dedup"]["variants"]) + 1
    assert dedup_key(**b) == dedup_key(**b) and len(dedup_key(**b)) == 64


@pytest.mark.parametrize("c", CLOUD, ids=lambda c: str(c["clear_pct"]))
def test_given_a_clear_percentage_then_publication_follows_the_80_percent_rule(c):
    from app.domain.vigor import is_scene_publishable

    assert is_scene_publishable(c["clear_pct"]) is c["publishable"]


@pytest.mark.parametrize("z", ANOMALY["zones"], ids=lambda z: f"{z['drop_score']}/{z['pixels']}")
def test_given_a_zone_drop_then_anomaly_follows_the_fixture_thresholds(z):
    from app.domain.anomaly import is_anomalous_zone

    p = ANOMALY["params"]
    assert is_anomalous_zone(z["drop_score"], z["pixels"], p["anomaly_drop"], p["anomaly_min_pixels"]) is z["anomalous"]


@pytest.mark.parametrize("r", ANOMALY["resolution"], ids=lambda r: str(r["recent_vigor"]))
def test_given_recent_scenes_then_resolution_needs_two_above_the_threshold(r):
    from app.domain.anomaly import is_resolved

    assert is_resolved(r["recent_vigor"], r["threshold"]) is r["resolved"]


@pytest.mark.parametrize("c", STATUS["cases"], ids=lambda c: c["name"])
def test_given_signals_then_the_parcel_status_matches(c):
    from app.domain.parcel_status import parcel_status

    s = parcel_status(c["signals"], dt.datetime.fromisoformat(c["now"]), c["doubts"])
    assert s["color"] == c["expected"]["color"] and s["reason_key"] == c["expected"]["reason_key"]
    assert [i["source"] for i in s["items"]] == c["expected"]["item_sources"]


def test_given_parcels_then_red_first_then_orange_then_green_with_ties_by_contributors_then_name():
    from app.domain.parcel_status import sort_parcels

    assert [p["id"] for p in sort_parcels(STATUS["sorting"]["parcels"])] == STATUS["sorting"]["expected"]


@pytest.mark.parametrize("c", RELIABILITY, ids=lambda c: f"{c['area_ha']}-{c['greenhouse']}")
def test_given_a_small_or_greenhouse_parcel_then_imagery_is_low_reliability(c):
    from app.domain.imagery_reliability import imagery_reliability

    assert imagery_reliability(c["area_ha"], c["greenhouse"], 0.3) == c["reliability"]


@pytest.mark.parametrize("c", NOTIFY["cases"], ids=lambda c: c["name"])
def test_given_a_frost_forecast_then_the_notification_is_scheduled_before_18h(c):
    from app.domain.notification_schedule import frost_notify_at

    at, late = frost_notify_at(c["forecast_day"], dt.datetime.fromisoformat(c["first_seen_at"]), c["notify_hour"])
    assert at == dt.datetime.fromisoformat(c["notify_at"]) and late is c["late"]

"""T034c - G1: parity of the worker view on every outgoing path (REST, export, reminders, F3 status payload); staff get the complete advice."""
import asyncio
import json
import os
import re
from pathlib import Path

import pytest

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    TODAY4,
    assert_worker_safe,
    call,
    export_of,
    seed_balance,
    seed_f4_rows,
    world4,
)

APP = Path(__file__).resolve().parents[2] / "app"
REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
ADVICE_WORKER_KEYS = {"parcel_id", "for_date", "kind", "total_minutes", "sectors", "net_need_mm", "stress_level", "confidence", "assumptions",
                      "unavailable_reason", "computed_at", "is_last_known", "ready_before_7"}
ADVICE_WORKER_REQUIRED = {"parcel_id", "for_date", "kind", "confidence", "assumptions", "computed_at"}


def _f(w):
    return f"/v1/farms/{w['farm_a']}"


def _assert_advice_worker(item):
    assert ADVICE_WORKER_REQUIRED <= set(item) and set(item) <= ADVICE_WORKER_KEYS, set(item) ^ ADVICE_WORKER_KEYS
    assert {a["key"] for a in item["assumptions"]} <= {"et0", "kc", "effective_rain", "efficiency", "application_rate", "rain_source"}


def test_given_a_worker_when_reading_one_advice_then_it_is_an_advice_worker_without_any_water_or_soil_key(client, token_for, world4):
    w = world4
    r = call(client, token_for(w["worker"]), "GET", f"{_f(w)}/parcels/{w['a1']}/irrigation/advice")
    assert r.status_code == 200, r.text
    _assert_advice_worker(r.json())
    assert_worker_safe(r.json(), "getAdvice")
    assert r.json()["total_minutes"] is not None  # the duration stays: the worker must execute it


def test_given_a_worker_when_listing_advice_then_every_item_is_an_advice_worker(client, token_for, world4):
    w = world4
    r = call(client, token_for(w["worker"]), "GET", f"{_f(w)}/irrigation/advice")
    assert r.status_code == 200 and len(r.json()["items"]) == 3
    for item in r.json()["items"]:
        _assert_advice_worker(item)
    assert_worker_safe(r.json(), "listAdvice")


def test_given_a_worker_when_reading_the_balance_then_no_reserve_or_moisture_key_is_served(client, token_for, world4):
    w = world4
    seed_balance(w["farm_a"], w["a1"])
    r = call(client, token_for(w["worker"]), "GET", f"{_f(w)}/parcels/{w['a1']}/irrigation/balance")
    assert r.status_code == 200 and r.json()["days"]
    assert_worker_safe(r.json(), "getBalance")
    assert {"depletion_mm", "etc_mm"} <= set(r.json()["days"][0])


@pytest.mark.parametrize("who", ["owner", "manager"])
def test_given_staff_then_the_responses_are_complete(client, token_for, world4, who):
    w = world4
    seed_balance(w["farm_a"], w["a1"])
    one = call(client, token_for(w[who]), "GET", f"{_f(w)}/parcels/{w['a1']}/irrigation/advice").json()
    assert "leaching_fraction" in one and {"ece_ds_m", "water_source", "analysis_age_days"} <= {a["key"] for a in one["assumptions"]}
    listed = call(client, token_for(w[who]), "GET", f"{_f(w)}/irrigation/advice").json()
    assert all("leaching_fraction" in i for i in listed["items"]) and len(listed["items"]) == 10
    day = call(client, token_for(w[who]), "GET", f"{_f(w)}/parcels/{w['a1']}/irrigation/balance").json()["days"][0]
    assert {"taw_mm", "raw_mm", "moisture_source"} <= set(day)


def test_given_a_worker_export_then_no_water_soil_or_salinity_key_exists_at_any_depth_and_staff_keep_the_plans(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    mine = export_of(w["worker"])
    assert_worker_safe(mine["irrigation"], "export")
    for plan in mine["irrigation"].get("plans", []):
        _assert_advice_worker({**plan, "assumptions": plan.get("assumptions", plan.get("worker_assumptions", []))})
    staff = export_of(w["owner"])["irrigation"]["plans"]
    assert staff and all("leaching_fraction" in p and "assumptions" in p for p in staff)


def test_given_the_morning_reminders_for_a_worker_then_the_payload_carries_no_analysis_soil_or_salinity_key(world4):
    from app.db.session import sessionmaker
    from app.irrigation.reminders import reminder_payload, reminder_targets

    w = world4

    async def run():
        async with sessionmaker() as s:
            return await reminder_targets(s, w["farm_a"], TODAY4)

    targets = [t for t in asyncio.run(run()) if t["user_id"] == w["worker"]]
    assert {str(t["parcel_id"]) for t in targets} == {str(p) for p in w["p"][:3]}
    for t in targets:
        payload = reminder_payload(t, "worker")
        assert_worker_safe(payload, "reminder")
        assert "leaching_fraction" not in json.dumps(payload) and "assumptions" not in json.dumps(payload)
    staff = [reminder_payload(t, "owner") for t in asyncio.run(run()) if t["user_id"] == w["owner"]]
    assert staff  # staff are reminded for every irrigated parcel of the farm


def test_given_the_f3_status_payload_for_a_worker_then_only_the_minutes_param_is_carried(client, token_for, world4):
    w = world4
    sql("INSERT INTO parcel_status_items (id, farm_id, parcel_id, source, severity, reason_key, reason_params, source_ref, observed_at)"
        " VALUES (gen_random_uuid(),$1,$2,'irrigation_need','act','status.irrigation_needed','{\"minutes\": 90}'::jsonb,gen_random_uuid(),now())", w["farm_a"], w["a1"])
    r = call(client, token_for(w["worker"]), "GET", f"{_f(w)}/parcels/{w['a1']}/status")
    assert r.status_code == 200
    assert_worker_safe(r.json(), "status")
    for item in r.json()["items"]:
        assert set(item.get("reason_params", {})) <= {"minutes"}


def test_given_the_f4_outgoing_sources_then_every_path_that_serves_plans_goes_through_worker_view():
    files = sorted((APP / "irrigation").glob("*.py")) + [APP / "routers" / "irrigation_advice.py", APP / "accounts" / "export.py",
                                                          REPO / "services/workers/tasks/send_irrigation_reminders.py"]
    serving = [p for p in files if p.exists() and re.search(r"irrigation_plans|worker_assumptions", p.read_text(encoding="utf-8"))]
    assert {p.name for p in serving} >= {"export.py", "send_irrigation_reminders.py"}, [p.name for p in serving]
    for p in serving:
        if p.name in ("worker_view.py", "lifecycle.py", "plans.py", "access.py"):
            continue  # producers / purge: the view itself, the writer of the column, the predicate
        text = p.read_text(encoding="utf-8")
        assert "worker_view" in text or "advice_view" in text, f"{p.name} serves plans without the worker view"

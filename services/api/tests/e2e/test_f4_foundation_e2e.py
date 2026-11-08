"""T034 - foundations on the running stack: a worker with 3 parcels out of 10 only sees their scope (advice, consumption, reminder);
archiving removes a parcel everywhere; empty gateways read 'unavailable'; empty referentials give `unavailable`; the clock is injected;
phone numbers are unique per run and no protected table is ever deleted from."""
import httpx

from tests.e2e._f4 import (
    BASE,
    NOW,
    farm_with_worker,
    run_job,
    seed_crop_without_irrigation_params,
    seed_event,
    seed_forecast,
    unique_phone,
)
from tests.helpers import sql

WORKER_FORBIDDEN = ("ece", "ecw", "salin", "water_source", "analysis_age", "soil", "taw", "raw", "moisture", "leaching", "cost")


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            if k == "key" and isinstance(v, str):
                yield v
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def test_given_unique_phones_per_call_then_two_numbers_never_collide():
    assert len({unique_phone() for _ in range(200)}) == 200


def test_given_a_worker_with_3_of_10_parcels_when_reading_advice_consumption_and_reminders_then_only_their_scope_is_served() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c)
        farm, mine, hidden = s["farm"], s["mine"], s["hidden"]
        for i, p in enumerate(s["parcels"]):
            seed_event(farm, p, s["owner_id"], volume=10.0 * (i + 1))
        advice = c.get(f"/farms/{farm}/irrigation/advice", headers=s["wh"])
        assert advice.status_code == 200, advice.text
        assert {i["parcel_id"] for i in advice.json()["items"]} == set(mine)
        assert advice.json()["to_irrigate_count"] <= 3
        cons = c.get(f"/farms/{farm}/irrigation/consumption", headers=s["wh"]).json()
        assert {p["parcel_id"] for p in cons["parcels"]} == set(mine) and abs(cons["total_m3"] - 60.0) < 1e-6
        assert hidden not in str(advice.json()) + str(cons)
        owner_cons = c.get(f"/farms/{farm}/irrigation/consumption", headers=s["oh"]).json()
        assert len(owner_cons["parcels"]) == 10 and abs(owner_cons["total_m3"] - 550.0) < 1e-6
        assert c.get(f"/farms/{farm}/parcels/{hidden}/irrigation/advice", headers=s["wh"]).json() == {"detail": "not_found"}
        assert not [k for k in _keys(advice.json()) if k.lower().startswith(WORKER_FORBIDDEN)]
        done = run_job("send_irrigation_reminders", farm_id=farm, now=NOW)
        by_user = {t["user_id"]: set(t["parcel_ids"]) for t in done["targets"]}
        assert by_user[s["worker_id"]] == set(mine) and by_user[s["owner_id"]] == set(s["parcels"])


def test_given_an_archived_parcel_then_it_disappears_from_every_path_of_the_worker() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c)
        farm, gone = s["farm"], s["mine"][0]
        before = c.get(f"/farms/{farm}/irrigation/advice", headers=s["wh"]).json()
        assert gone in {i["parcel_id"] for i in before["items"]}
        assert c.delete(f"/farms/{farm}/fields/{gone}", headers=s["oh"]).status_code == 204  # archive
        after = c.get(f"/farms/{farm}/irrigation/advice", headers=s["wh"]).json()
        assert gone not in {i["parcel_id"] for i in after["items"]}
        assert c.get(f"/farms/{farm}/parcels/{gone}/irrigation/advice", headers=s["wh"]).status_code == 404
        assert gone not in {p["parcel_id"] for p in c.get(f"/farms/{farm}/irrigation/consumption", headers=s["wh"]).json()["parcels"]}
        done = run_job("send_irrigation_reminders", farm_id=farm, now=NOW)
        assert all(gone not in t["parcel_ids"] for t in done["targets"])
        planned = run_job("compute_irrigation_plans", farm_id=farm, now=NOW)
        assert gone not in [str(p) for p in planned["parcels"]]
        assert sql("SELECT count(*) FROM irrigation_plans WHERE parcel_id=$1", __import__("uuid").UUID(gone))[0][0] == 0


def test_given_empty_gateways_then_the_advice_is_unavailable_and_nothing_is_invented() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=4, assigned=2)
        run_job("compute_irrigation_plans", farm_id=s["farm"], now=NOW)
        r = c.get(f"/farms/{s['farm']}/parcels/{s['mine'][0]}/irrigation/advice", headers=s["oh"])
        assert r.status_code == 200 and r.json()["kind"] == "unavailable" and r.json()["unavailable_reason"] in ("gateway_not_configured", "no_weather")
        assert r.json()["total_minutes"] is None and r.json()["net_need_mm"] is None
        weather = c.get(f"/farms/{s['farm']}/weather", headers=s["wh"]).json()
        assert weather["availability"] == "unavailable" and weather["reason"] == "gateway_not_configured" and not weather.get("days")


def test_given_empty_referentials_and_a_forecast_then_the_advice_is_unavailable_with_a_reason_and_no_default_coefficient() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=3, assigned=2)
        seed_forecast(s["farm"])
        seed_crop_without_irrigation_params(s["farm"], s["mine"][0])
        run_job("compute_irrigation_plans", farm_id=s["farm"], now=NOW)
        r = c.get(f"/farms/{s['farm']}/parcels/{s['mine'][0]}/irrigation/advice", headers=s["oh"])
        assert r.status_code == 200 and r.json()["kind"] == "unavailable" and r.json()["unavailable_reason"] == "no_crop_coefficient"
        assert r.json()["total_minutes"] is None and not any(a["key"] == "kc" for a in r.json()["assumptions"])


def test_given_the_injected_clock_then_the_plan_is_dated_on_the_local_day_and_ready_before_7() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=3, assigned=2)
        seed_forecast(s["farm"])
        run_job("compute_irrigation_plans", farm_id=s["farm"], now=NOW)
        r = c.get(f"/farms/{s['farm']}/parcels/{s['mine'][0]}/irrigation/advice", headers=s["oh"]).json()
        assert r["for_date"] == "2026-06-04" and r["ready_before_7"] is True
        late = run_job("compute_irrigation_plans", farm_id=s["farm"], now="2026-06-04T08:00:00+00:00")  # 09:00 local
        assert late["ready_before_7"] is False

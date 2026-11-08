"""T023 - G1b: the `irrigation_need` reader of recompute_status turns today's plan into a parcel-status signal.
Time is injected (`now` argument); rows are unique per test and never deleted."""
import datetime as dt
import json
import uuid

import pytest

from tasks.recompute_status import recompute_status
from tests._f3 import run, seed_farm, seed_parcel

NOW = dt.datetime(2026, 6, 4, 9, 0, tzinfo=dt.UTC)
DAY = dt.date(2026, 6, 4)


async def _plan(conn, farm, parcel, kind, *, minutes=None, stress=None, computed_at=None, reason=None):
    await conn.execute(
        "INSERT INTO irrigation_plans (id, farm_id, parcel_id, for_date, kind, total_minutes, sectors, stress_level, confidence, assumptions, worker_assumptions, unavailable_reason, computed_at, ready_before_7)"
        " VALUES ($1,$2,$3,$4,$5,$6,'[]'::jsonb,$7,'medium','[]'::jsonb,'[]'::jsonb,$8,$9,true)",
        uuid.uuid4(), farm, parcel, DAY, kind, minutes, stress, reason, computed_at or NOW - dt.timedelta(hours=2))


async def _status(conn, parcel):
    row = await conn.fetchrow("SELECT color, reason_key FROM parcel_status WHERE parcel_id = $1", parcel)
    items = [dict(i) for i in await conn.fetch("SELECT source, severity, reason_key, reason_params, observed_at FROM parcel_status_items WHERE parcel_id = $1 AND source = 'irrigation_need'", parcel)]
    for i in items:
        i["reason_params"] = json.loads(i["reason_params"]) if isinstance(i["reason_params"], str) else i["reason_params"]
    return dict(row), items


def _case(kind, **plan):
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _plan(conn, farm, parcel, kind, **plan)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    return run(scenario)


def test_given_an_irrigate_plan_then_the_parcel_acts_with_the_minutes_and_the_plan_date_as_observation():
    status, items = _case("irrigate", minutes=120)
    assert status["color"] == "red"
    assert len(items) == 1 and items[0]["severity"] == "act" and items[0]["reason_key"] == "status.irrigation_needed"
    assert items[0]["reason_params"] == {"minutes": 120}
    assert items[0]["observed_at"] == NOW - dt.timedelta(hours=2)  # observed_at = computed_at


@pytest.mark.parametrize("kind", ["postpone_rain", "no_need"])
def test_given_a_postponed_or_no_need_plan_then_the_parcel_is_ok_and_no_irrigation_item_is_listed(kind):
    status, items = _case(kind)
    assert status["color"] == "green" and items == []


def test_given_a_high_rainfed_stress_then_the_parcel_acts_with_water_stress():
    status, items = _case("rainfed_stress", stress="high")
    assert status["color"] == "red" and [(i["severity"], i["reason_key"]) for i in items] == [("act", "status.water_stress")]


def test_given_a_watch_rainfed_stress_then_the_parcel_watches():
    status, items = _case("rainfed_stress", stress="watch")
    assert status["color"] == "orange" and [(i["severity"], i["reason_key"]) for i in items] == [("watch", "status.water_stress")]


def test_given_a_none_rainfed_stress_then_nothing_is_signalled():
    status, items = _case("rainfed_stress", stress="none")
    assert items == [] and status["color"] == "green"


def test_given_an_unavailable_plan_then_no_signal_is_emitted_and_the_parcel_is_not_turned_red():
    status, items = _case("unavailable", reason="no_crop_coefficient")
    assert items == [] and status["color"] != "red"


def test_given_a_signal_older_than_24_hours_with_the_injected_clock_then_it_is_expired():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _plan(conn, farm, parcel, "irrigate", minutes=60, computed_at=NOW - dt.timedelta(hours=23))
        await recompute_status({}, NOW, farm_id=farm)
        fresh = await _status(conn, parcel)
        await recompute_status({}, NOW + dt.timedelta(hours=2), farm_id=farm)  # 25 h after the plan
        return fresh, await _status(conn, parcel)

    (fresh, _), (_, stale_items) = run(scenario)
    assert fresh["color"] == "red" and stale_items == []


def test_given_an_archived_parcel_then_no_signal_is_produced():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm, archived=True)
        await _plan(conn, farm, parcel, "irrigate", minutes=90)
        await recompute_status({}, NOW, farm_id=farm)
        return await conn.fetchval("SELECT count(*) FROM parcel_status_items WHERE parcel_id = $1", parcel)

    assert run(scenario) == 0


def test_given_two_recomputes_for_the_same_parcel_then_the_items_are_deduplicated():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _plan(conn, farm, parcel, "irrigate", minutes=45)
        await recompute_status({}, NOW, farm_id=farm)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    _, items = run(scenario)
    assert len(items) == 1


def test_given_the_task_source_then_it_reads_the_plans_through_the_shared_predicate_and_the_clock_is_injected():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "tasks" / "recompute_status.py").read_text(encoding="utf-8")
    assert "irrigation_need" in text and "irrigation_plans" in text and "VISIBLE_PARCELS_SQL" in text

"""T069 - R5-A1..A5: the colour combines weather alerts, vigor anomaly and overdue operations (F6); F4/F5 are absent without error; per-farm lock; archived parcels skipped."""
import asyncio
import datetime as dt
import uuid

import asyncpg

from tasks.recompute_status import recompute_status
from tests._f3 import DSN, TODAY, day, run, seed_crop, seed_farm, seed_parcel, seed_season, seed_threshold, seed_weather

NOW = dt.datetime.combine(TODAY, dt.time(9, 0), tzinfo=dt.UTC)


async def _status(conn, parcel):
    r = await conn.fetchrow("SELECT color, reason_key, rank, imagery_reliability, computed_at FROM parcel_status WHERE parcel_id = $1", parcel)
    items = [dict(i) for i in await conn.fetch("SELECT source, severity, reason_key, observed_at, source_ref FROM parcel_status_items WHERE parcel_id = $1", parcel)]
    return (dict(r) if r else None), items


async def _alert(conn, farm, parcel, severity="critical"):
    aid = uuid.uuid4()
    await conn.execute(
        "INSERT INTO alerts (id, farm_id, parcel_id, type, severity, status, forecast_day, reason_key, dedup_key) VALUES ($1,$2,$3,'frost',$4,'active',$5,'alert.frost',$6)",
        aid, farm, parcel, severity, TODAY + dt.timedelta(days=2), f"dk-{aid}")
    return aid


async def _zone(conn, farm, parcel, status="open"):
    zid = uuid.uuid4()
    await conn.execute(
        "INSERT INTO attention_zones (id, farm_id, parcel_id, geometry, centroid, detected_on, status, reason_key)"
        " VALUES ($1,$2,$3,ST_GeomFromText('POLYGON((-7.6 33.57,-7.599 33.57,-7.599 33.571,-7.6 33.57))',4326),ST_GeomFromText('POINT(-7.5995 33.5705)',4326),$4,$5,'zone.fixture')",
        zid, farm, parcel, TODAY, status)
    return zid


async def _overdue_operation(conn, farm, parcel, days_ago=2):
    op = uuid.uuid4()
    on = TODAY - dt.timedelta(days=days_ago)
    await conn.execute("INSERT INTO operations (id, farm_id, type, performed_on, status) VALUES ($1,$2,'irrigation',$3,'planned')", op, farm, on)
    await conn.execute("INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, type, performed_on, status) VALUES ($1,$2,$3,$4,'irrigation',$5,'planned')", uuid.uuid4(), farm, op, parcel, on)
    return op


def test_given_a_parcel_without_any_signal_when_computing_then_it_is_green_with_nothing_to_do_and_no_contributor():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, items = run(scenario)
    assert (status["color"], status["reason_key"]) == ("green", "status.nothing_to_do") and items == []


def test_given_a_critical_frost_alert_when_computing_then_the_parcel_is_red_and_the_contributor_names_the_weather_alert_with_its_server_reference():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        aid = await _alert(conn, farm, parcel)
        await recompute_status({}, NOW, farm_id=farm)
        return (*await _status(conn, parcel), aid)

    status, items, aid = run(scenario)
    assert status["color"] == "red" and [(i["source"], i["severity"], i["source_ref"]) for i in items] == [("weather_alert", "act", aid)]


def test_given_an_overdue_planned_operation_f6_when_computing_then_the_parcel_is_orange_with_the_overdue_source():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        op = await _overdue_operation(conn, farm, parcel)
        await recompute_status({}, NOW, farm_id=farm)
        return (*await _status(conn, parcel), op)

    status, items, op = run(scenario)
    assert status["color"] == "orange" and [(i["source"], i["source_ref"]) for i in items] == [("overdue_operations", op)]


def test_given_a_planned_operation_not_yet_due_when_computing_then_it_does_not_contribute():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _overdue_operation(conn, farm, parcel, days_ago=-3)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, items = run(scenario)
    assert status["color"] == "green" and items == []


def test_given_weather_vigor_and_overdue_signals_together_when_computing_then_all_contribute_and_the_most_severe_drives_the_colour_and_reason():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _alert(conn, farm, parcel)
        await _zone(conn, farm, parcel)
        await _overdue_operation(conn, farm, parcel)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, items = run(scenario)
    assert {i["source"] for i in items} == {"weather_alert", "vigor_anomaly", "overdue_operations"}
    assert status["color"] == "red" and status["reason_key"] == "status.frost"


def test_given_irrigation_and_health_sources_not_delivered_when_computing_then_no_error_and_no_item_for_them():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _alert(conn, farm, parcel, severity="warning")
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, items = run(scenario)
    assert status["color"] == "orange" and {i["source"] for i in items}.isdisjoint({"irrigation_need", "health_risk"})


def test_given_a_greenhouse_parcel_with_a_vigor_zone_when_computing_then_the_unreliable_imagery_does_not_contribute_and_is_flagged_low():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm, greenhouse=True)
        await _zone(conn, farm, parcel)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, items = run(scenario)
    assert status["imagery_reliability"] == "low" and "vigor_anomaly" not in {i["source"] for i in items}


def test_given_a_reliable_parcel_with_an_open_vigor_zone_when_computing_then_it_is_orange_with_the_vigor_source():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        zone = await _zone(conn, farm, parcel)
        await recompute_status({}, NOW, farm_id=farm)
        return (*await _status(conn, parcel), zone)

    status, items, zone = run(scenario)
    assert status["color"] == "orange" and [(i["source"], i["source_ref"]) for i in items] == [("vigor_anomaly", zone)]


def test_given_a_freezing_forecast_and_no_validated_threshold_when_computing_then_the_doubt_makes_the_parcel_orange_never_green():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        crop_id, slug = await seed_crop(conn)
        await seed_season(conn, farm, parcel, crop_id)
        await seed_weather(conn, farm, [day(1, tmin=-3)])
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, _ = run(scenario)
    assert status["color"] == "orange"


def test_given_a_freezing_forecast_with_a_threshold_not_reached_when_computing_then_the_parcel_stays_green():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        crop_id, slug = await seed_crop(conn)
        await seed_threshold(conn, slug, frost_c=-8)
        await seed_season(conn, farm, parcel, crop_id)
        await seed_weather(conn, farm, [day(1, tmin=-3)])
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    assert run(scenario)[0]["color"] == "green"


def test_given_several_parcels_when_computing_then_the_rank_puts_red_then_orange_then_green():
    async def scenario(conn):
        farm = await seed_farm(conn)
        green, orange, red = [await seed_parcel(conn, farm) for _ in range(3)]
        await _alert(conn, farm, red)
        await _overdue_operation(conn, farm, orange)
        await recompute_status({}, NOW, farm_id=farm)
        ranks = {c: (await _status(conn, p))[0]["rank"] for c, p in (("green", green), ("orange", orange), ("red", red))}
        return ranks

    r = run(scenario)
    assert r["red"] < r["orange"] < r["green"]


def test_given_an_archived_parcel_when_computing_then_no_status_is_written_for_it():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm, archived=True)
        await _alert(conn, farm, parcel)
        await recompute_status({}, NOW, farm_id=farm)
        return await _status(conn, parcel)

    status, items = run(scenario)
    assert status is None and items == []


def test_given_the_monitoring_lock_held_by_another_run_when_computing_then_the_recompute_waits_for_it():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        other = await asyncpg.connect(DSN)
        tx = other.transaction()
        await tx.start()
        await other.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"monitoring:{farm}")
        task = asyncio.create_task(recompute_status({}, NOW, farm_id=farm))
        await asyncio.sleep(1.0)
        waited = not task.done()
        await tx.commit()
        await other.close()
        await asyncio.wait_for(task, 15)
        return waited, (await _status(conn, parcel))[0]["color"]

    assert run(scenario) == (True, "green")


def test_given_the_worker_settings_then_the_status_recompute_runs_at_least_hourly():
    import worker
    from tasks import recompute_status as mod

    crons = [c for c in worker.WorkerSettings.cron_jobs if c.coroutine is mod.recompute_status]
    assert crons and crons[0].hour is None

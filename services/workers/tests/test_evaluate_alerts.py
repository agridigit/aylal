"""T048 - R2-A1..A4: weather alerts per crop and stage; fixture thresholds only (no agronomic value is seeded); frost notified before 18:00 the evening before."""
import datetime as dt

from tasks.evaluate_alerts import evaluate_alerts
from tests._f3 import TODAY, alerts_of, day, run, seed_crop, seed_farm, seed_parcel, seed_season, seed_threshold, seed_weather

NOW = dt.datetime.combine(TODAY, dt.time(9, 0), tzinfo=dt.UTC)


async def _setup(conn, days, *, frost_c=-2, stage="fixture_flowering", thresholds=True, archived=False):
    farm = await seed_farm(conn)
    parcel = await seed_parcel(conn, farm, archived=archived)
    crop_id, slug = await seed_crop(conn)
    if thresholds:
        await seed_threshold(conn, slug, frost_c=frost_c)
    await seed_season(conn, farm, parcel, crop_id, stage=stage)
    await seed_weather(conn, farm, days)
    return farm, parcel, slug


def test_given_a_frost_forecast_at_48_hours_on_a_sensitive_stage_when_evaluating_then_the_alert_is_notified_the_evening_before_before_18h():
    async def scenario(conn):
        farm, parcel, slug = await _setup(conn, [day(2, tmin=-5)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm), parcel, slug

    (a,), parcel, slug = run(scenario)
    assert (a["type"], a["severity"], a["status"], a["parcel_id"], a["crop_slug"]) == ("frost", "critical", "active", parcel, slug)
    local = a["notify_at"].astimezone(dt.timezone(dt.timedelta(hours=1)))
    assert local.date() == TODAY + dt.timedelta(days=1) and local.hour == 17 and a["notified_at"] is None


def test_given_a_stage_without_a_frost_threshold_when_a_hard_frost_is_forecast_then_no_frost_alert_is_emitted():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-5)], frost_c=None)  # dormant stage: no frost threshold
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm)

    assert run(scenario) == []


def test_given_a_frost_forecast_above_the_threshold_when_evaluating_then_no_alert_is_emitted():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=4)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm)

    assert run(scenario) == []


def test_given_a_crop_without_any_validated_threshold_when_evaluating_then_no_alert_is_invented_even_for_a_hard_frost():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-9)], thresholds=False)
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm)

    assert run(scenario) == []


def test_given_chergui_heavy_rain_and_strong_wind_forecasts_when_evaluating_then_each_type_is_created_with_parcel_severity_and_reason():
    async def scenario(conn):
        farm, parcel, _ = await _setup(conn, [day(1, tmax=41, humidity_pct=20, wind_kmh=26), day(2, rain_mm=55), day(3, wind_kmh=45)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm), parcel

    rows, parcel = run(scenario)
    assert {a["type"] for a in rows} >= {"chergui", "heavy_rain", "strong_wind"}
    assert all(a["parcel_id"] == parcel and a["severity"] in ("info", "warning", "critical") and a["reason_key"] for a in rows)


def test_given_a_strong_wind_forecast_when_evaluating_then_the_alert_advises_not_to_spray():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(1, wind_kmh=45)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm)

    wind = [a for a in run(scenario) if a["type"] == "strong_wind"]
    assert wind and wind[0]["advice_key"] == "do_not_spray"


def test_given_an_archived_parcel_when_evaluating_then_no_alert_is_generated():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-5)], archived=True)
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await alerts_of(conn, farm)

    assert run(scenario) == []


def test_given_two_active_crops_on_one_parcel_when_evaluating_then_each_crop_has_its_own_alert():
    async def scenario(conn):
        farm, parcel, slug1 = await _setup(conn, [day(2, tmin=-5)])
        crop2, slug2 = await seed_crop(conn)
        await seed_threshold(conn, slug2, frost_c=-1)
        await seed_season(conn, farm, parcel, crop2)
        await evaluate_alerts({}, NOW, farm_id=farm)
        return {a["crop_slug"] for a in await alerts_of(conn, farm)}, {slug1, slug2}

    got, expected = run(scenario)
    assert got == expected


def test_given_the_same_forecast_evaluated_twice_when_evaluating_then_no_duplicate_alert_is_created():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-5)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        await evaluate_alerts({}, NOW + dt.timedelta(hours=3), farm_id=farm)
        return await alerts_of(conn, farm)

    rows = run(scenario)
    assert len(rows) == 1 and rows[0]["revision"] == 1


def test_given_a_notified_frost_when_the_same_severity_is_re_evaluated_then_notified_at_is_kept_so_no_second_notification_is_sent():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-5)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        await conn.execute("UPDATE alerts SET notified_at = now() WHERE farm_id = $1", farm)
        await evaluate_alerts({}, NOW + dt.timedelta(hours=3), farm_id=farm)
        return await alerts_of(conn, farm)

    (a,) = run(scenario)
    assert a["notified_at"] is not None


def test_given_a_notified_frost_when_the_forecast_gets_colder_then_the_severity_grows_the_revision_increments_and_a_new_notification_is_due():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-2.5)])  # warning: under 1 degree below the threshold
        await evaluate_alerts({}, NOW, farm_id=farm)
        await conn.execute("UPDATE alerts SET notified_at = now() WHERE farm_id = $1", farm)
        await seed_weather(conn, farm, [day(2, tmin=-6)])
        await evaluate_alerts({}, NOW + dt.timedelta(hours=3), farm_id=farm)
        return await alerts_of(conn, farm)

    (a,) = run(scenario)
    assert a["severity"] == "critical" and a["revision"] == 2 and a["notified_at"] is None


def test_given_a_forecast_that_disappears_when_evaluating_then_the_alert_is_resolved_and_a_passed_day_is_expired():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-5), day(0, tmin=-5)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        await seed_weather(conn, farm, [day(2, tmin=5)])
        await evaluate_alerts({}, NOW + dt.timedelta(days=1, hours=3), farm_id=farm)
        return await alerts_of(conn, farm)

    by_day = {a["forecast_day"]: a["status"] for a in run(scenario)}
    assert by_day[TODAY] == "expired" and by_day[TODAY + dt.timedelta(days=2)] == "resolved"


def test_given_a_dismissed_alert_when_the_forecast_stays_then_it_is_not_reactivated():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(2, tmin=-5)])
        await evaluate_alerts({}, NOW, farm_id=farm)
        await conn.execute("UPDATE alerts SET status = 'dismissed' WHERE farm_id = $1", farm)
        await evaluate_alerts({}, NOW + dt.timedelta(hours=3), farm_id=farm)
        return await alerts_of(conn, farm)

    assert [a["status"] for a in run(scenario)] == ["dismissed"]


def test_given_20_active_alerts_on_a_parcel_when_a_new_one_is_due_then_it_is_not_created():
    async def scenario(conn):
        farm, *_ = await _setup(conn, [day(i, tmin=-5) for i in range(1, 8)] + [day(i, wind_kmh=45) for i in range(1, 2)])
        parcel = (await conn.fetchrow("SELECT id FROM parcels WHERE farm_id = $1", farm))["id"]
        for i in range(20):
            await conn.execute(
                "INSERT INTO alerts (id, farm_id, parcel_id, type, severity, status, forecast_day, reason_key, dedup_key)"
                " SELECT gen_random_uuid(), $1, $2, 'chergui', 'info', 'active', $3, 'alert.fixture', $4", farm, parcel, TODAY + dt.timedelta(days=30 + i), f"cap-{farm}-{i}")
        await evaluate_alerts({}, NOW, farm_id=farm)
        return await conn.fetchval("SELECT count(*) FROM alerts WHERE parcel_id = $1 AND status = 'active'", parcel)

    assert run(scenario) == 20

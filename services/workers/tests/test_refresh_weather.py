"""T041 - R1-A1, R1-A2: one gateway call per 0.1 degree cell and per 3 hours (Redis lock), only rounded coordinates leave, nothing invented when unavailable."""
import datetime as dt
import json
import random

import tasks.refresh_weather as rw
from tasks.refresh_weather import refresh_weather
from tests._f3 import day, run, seed_farm


class SpyGateway:
    def __init__(self, configured=True):
        self._configured, self.calls = configured, []

    def configured(self):
        return self._configured

    def fetch(self, *, lat_r, lon_r):
        self.calls.append({"lat_r": lat_r, "lon_r": lon_r})
        return {"availability": "ok", "days": [{k: v for k, v in day(i).items()} for i in range(8)]}


def _cell():
    lat_r, lon_r = round(20 + random.randint(0, 400) / 10, 1), round(-1 - random.randint(0, 120) / 10, 1)
    return lat_r, lon_r


def _mine(spy, lat_r, lon_r):
    return [c for c in spy.calls if (c["lat_r"], c["lon_r"]) == (lat_r, lon_r)]


async def _row(conn, farm):
    r = await conn.fetchrow("SELECT availability, reason, fetched_at, days FROM farm_weather WHERE farm_id = $1", farm)
    return dict(r, days=json.loads(r["days"]) if isinstance(r["days"], str) else r["days"])


def test_given_two_farms_in_the_same_cell_when_refreshing_then_the_gateway_is_called_once_and_both_get_8_dated_days():
    lat_r, lon_r = _cell()
    spy = SpyGateway()

    async def scenario(conn):
        f1 = await seed_farm(conn, lat=lat_r + 0.03, lon=lon_r + 0.02)
        f2 = await seed_farm(conn, lat=lat_r - 0.04, lon=lon_r - 0.01)
        await refresh_weather({"gateway": spy}, dt.datetime.now(dt.UTC))
        return await _row(conn, f1), await _row(conn, f2)

    r1, r2 = run(scenario)
    assert len(_mine(spy, lat_r, lon_r)) == 1
    for r in (r1, r2):
        assert r["availability"] == "ok" and r["fetched_at"] is not None and len(r["days"]) == 8 and r["days"][0]["icon"]


def test_given_a_cell_already_refreshed_less_than_3_hours_ago_when_refreshing_again_then_no_new_call_is_made_and_the_forecast_is_kept():
    lat_r, lon_r = _cell()
    spy = SpyGateway()

    async def scenario(conn):
        farm = await seed_farm(conn, lat=lat_r, lon=lon_r)
        now = dt.datetime.now(dt.UTC)
        await refresh_weather({"gateway": spy}, now)
        first = await _row(conn, farm)
        await refresh_weather({"gateway": spy}, now + dt.timedelta(minutes=30))
        return first, await _row(conn, farm)

    first, second = run(scenario)
    assert len(_mine(spy, lat_r, lon_r)) == 1 and second["days"] == first["days"] and second["fetched_at"] == first["fetched_at"]


def test_given_a_located_farm_when_calling_the_gateway_then_only_the_rounded_cell_is_sent_never_the_exact_position():
    lat_r, lon_r = _cell()
    spy = SpyGateway()

    async def scenario(conn):
        await seed_farm(conn, lat=lat_r + 0.0312, lon=lon_r + 0.0287)
        await refresh_weather({"gateway": spy}, dt.datetime.now(dt.UTC))

    run(scenario)
    sent = _mine(spy, lat_r, lon_r)
    assert sent == [{"lat_r": lat_r, "lon_r": lon_r}]
    assert all(round(v, 1) == v for c in spy.calls for v in c.values())


def test_given_no_configured_gateway_when_refreshing_then_the_last_dated_forecast_is_kept_and_marked_unavailable_with_a_reason():
    lat_r, lon_r = _cell()
    ok, off = SpyGateway(), SpyGateway(configured=False)

    async def scenario(conn):
        farm = await seed_farm(conn, lat=lat_r, lon=lon_r)
        await refresh_weather({"gateway": ok}, dt.datetime.now(dt.UTC))
        before = await _row(conn, farm)
        await refresh_weather({"gateway": off}, dt.datetime.now(dt.UTC))
        return before, await _row(conn, farm)

    before, after = run(scenario)
    assert after["availability"] == "unavailable" and after["reason"] == "gateway_not_configured"
    assert after["days"] == before["days"] and after["fetched_at"] == before["fetched_at"]
    assert off.calls == []


def test_given_a_farm_without_location_when_refreshing_then_no_call_is_made_and_the_reason_is_farm_not_located_with_no_value():
    spy = SpyGateway()

    async def scenario(conn):
        farm = await seed_farm(conn)
        await refresh_weather({"gateway": spy}, dt.datetime.now(dt.UTC))
        return await _row(conn, farm)

    r = run(scenario)
    assert r["availability"] == "unavailable" and r["reason"] == "farm_not_located" and r["days"] == [] and r["fetched_at"] is None


def test_given_the_daily_budget_spent_when_refreshing_then_no_call_is_made_and_the_previous_forecast_is_kept(monkeypatch):
    lat_r, lon_r = _cell()
    spy = SpyGateway()

    async def scenario(conn):
        farm = await seed_farm(conn, lat=lat_r, lon=lon_r)
        await conn.execute("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,$2,now() - interval '5 hours','ok',$3::jsonb)",
                           farm, f"{lat_r}:{lon_r}", json.dumps([day(0)]))
        monkeypatch.setattr(rw, "DAILY_BUDGET", 0)
        await refresh_weather({"gateway": spy}, dt.datetime.now(dt.UTC))
        return await _row(conn, farm)

    r = run(scenario)
    assert _mine(spy, lat_r, lon_r) == [] and len(r["days"]) == 1


def test_given_the_worker_settings_then_the_weather_refresh_is_registered_and_scheduled():
    import worker

    assert rw.refresh_weather in worker.WorkerSettings.functions
    assert rw.refresh_weather in [c.coroutine for c in worker.WorkerSettings.cron_jobs]

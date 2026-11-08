"""T080 - R7-A1, R7-A2: one summary row per active recipient at their hour, limited to their scope, in their language, with the weather of the day."""
import datetime as dt
import json
import uuid

from tasks.send_daily_summary import send_daily_summary
from tests._f3 import TODAY, day, run, seed_farm, seed_parcel, seed_weather

MOROCCO = dt.timezone(dt.timedelta(hours=1))


def _at(hour):
    """A UTC instant whose Morocco local time is `hour`:05 today."""
    return dt.datetime.combine(TODAY, dt.time(hour, 5), tzinfo=MOROCCO).astimezone(dt.UTC)


async def _user(conn, farm, role, *, lang="fr", hour=None, removed=False):
    u = uuid.uuid4()
    await conn.execute("INSERT INTO users (id, phone_e164, status, language) VALUES ($1,$2,'active',$3)", u, f"+2126{uuid.uuid4().int % 10**8:08d}", lang)
    await conn.execute("INSERT INTO farm_members (farm_id, user_id, role, removed_at) VALUES ($1,$2,$3,$4)", farm, u, role, dt.datetime.now(dt.UTC) if removed else None)
    if hour is not None:
        await conn.execute("INSERT INTO notification_prefs (farm_id, user_id, summary_hour, alerts_enabled) VALUES ($1,$2,$3,true)", farm, u, hour)
    return u


async def _status(conn, farm, parcel, color, rank=0):
    await conn.execute("INSERT INTO parcel_status (parcel_id, farm_id, color, reason_key, reason_params, rank, computed_at, data_age_at, imagery_reliability)"
                       " VALUES ($1,$2,$3,'status.fixture','{}'::jsonb,$4,now(),now(),'ok')", parcel, farm, color, rank)


async def _rows(conn, farm):
    out = {}
    for r in await conn.fetch("SELECT user_id, locale, payload, summary_date FROM daily_summaries WHERE farm_id = $1", farm):
        out[r["user_id"]] = dict(r, payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"])
    return out


async def _world(conn):
    farm = await seed_farm(conn, lat=33.57, lon=-7.6)
    owner = await _user(conn, farm, "owner", lang="ary")
    worker = await _user(conn, farm, "worker", lang="ar")
    idle = await _user(conn, farm, "worker", lang="fr")
    visible = await seed_parcel(conn, farm)
    hidden = await seed_parcel(conn, farm)
    calm = await seed_parcel(conn, farm)
    await _status(conn, farm, visible, "orange", 2)
    await _status(conn, farm, hidden, "red", 0)
    await _status(conn, farm, calm, "green", 5)
    await conn.execute("INSERT INTO worker_parcels (farm_id, user_id, parcel_id) VALUES ($1,$2,$3)", farm, worker, visible)
    return farm, owner, worker, idle, visible, hidden


def test_given_members_at_the_summary_hour_when_sending_then_exactly_one_row_per_active_member_is_created_even_without_parcels():
    async def scenario(conn):
        farm, owner, worker, idle, *_ = await _world(conn)
        await _user(conn, farm, "worker", removed=True)
        created = await send_daily_summary({}, _at(7), farm_id=farm)
        return created, set(await _rows(conn, farm)), {owner, worker, idle}

    created, got, expected = run(scenario)
    assert created == 3 and got == expected


def test_given_a_worker_when_sending_then_the_payload_holds_only_their_parcels_and_nothing_about_the_others():
    async def scenario(conn):
        farm, owner, worker, idle, visible, hidden = await _world(conn)
        await send_daily_summary({}, _at(7), farm_id=farm)
        rows = await _rows(conn, farm)
        return rows, owner, worker, idle, visible, hidden

    rows, owner, worker, idle, visible, hidden = run(scenario)
    assert [i["parcel_id"] for i in rows[worker]["payload"]["items"]] == [str(visible)]
    assert str(hidden) not in json.dumps(rows[worker]["payload"]) and rows[idle]["payload"]["items"] == []
    assert [i["color"] for i in rows[owner]["payload"]["items"]] == ["red", "orange"]


def test_given_an_invisible_parcel_changing_state_when_sending_then_the_worker_payload_is_identical():
    async def scenario(conn):
        farm, _, worker, _, _, hidden = await _world(conn)
        await send_daily_summary({}, _at(7), farm_id=farm)
        before = (await _rows(conn, farm))[worker]["payload"]
        await conn.execute("DELETE FROM daily_summaries WHERE farm_id = $1", farm)
        await conn.execute("UPDATE parcel_status SET color = 'green' WHERE parcel_id = $1", hidden)
        await send_daily_summary({}, _at(7), farm_id=farm)
        return before, (await _rows(conn, farm))[worker]["payload"]

    before, after = run(scenario)
    assert before == after


def test_given_each_user_language_when_sending_then_the_row_is_in_that_language():
    async def scenario(conn):
        farm, owner, worker, idle, *_ = await _world(conn)
        await send_daily_summary({}, _at(7), farm_id=farm)
        rows = await _rows(conn, farm)
        return {rows[owner]["locale"], rows[worker]["locale"], rows[idle]["locale"]}

    assert run(scenario) == {"ary", "ar", "fr"}


def test_given_a_stored_forecast_when_sending_then_the_weather_of_the_day_is_in_the_payload():
    async def scenario(conn):
        farm, owner, *_ = await _world(conn)
        await seed_weather(conn, farm, [day(0, icon="rain"), day(1)])
        await send_daily_summary({}, _at(7), farm_id=farm)
        return (await _rows(conn, farm))[owner]["payload"]

    assert run(scenario)["weather_code"] == "rain"


def test_given_no_forecast_when_sending_then_the_weather_code_is_null_and_nothing_is_invented():
    async def scenario(conn):
        farm, owner, *_ = await _world(conn)
        await send_daily_summary({}, _at(7), farm_id=farm)
        return (await _rows(conn, farm))[owner]["payload"]

    p = run(scenario)
    assert "weather_code" in p and p["weather_code"] is None


def test_given_a_member_with_their_own_hour_when_sending_then_only_the_members_at_that_hour_get_a_row():
    async def scenario(conn):
        farm, owner, worker, idle, *_ = await _world(conn)
        await conn.execute("INSERT INTO notification_prefs (farm_id, user_id, summary_hour, alerts_enabled) VALUES ($1,$2,18,true)", farm, worker)
        at7 = set(await _sent(conn, farm, 7))
        await conn.execute("DELETE FROM daily_summaries WHERE farm_id = $1", farm)
        at18 = set(await _sent(conn, farm, 18))
        return at7, at18, {owner, idle}, {worker}

    at7, at18, expected7, expected18 = run(scenario)
    assert at7 == expected7 and at18 == expected18


async def _sent(conn, farm, hour):
    await send_daily_summary({}, _at(hour), farm_id=farm)
    return list(await _rows(conn, farm))


def test_given_a_summary_already_stored_when_sending_again_then_nothing_is_duplicated():
    async def scenario(conn):
        farm, *_ = await _world(conn)
        first = await send_daily_summary({}, _at(7), farm_id=farm)
        again = await send_daily_summary({}, _at(7), farm_id=farm)
        return first, again, await conn.fetchval("SELECT count(*) FROM daily_summaries WHERE farm_id = $1", farm)

    assert run(scenario) == (3, 0, 3)


def test_given_an_archived_parcel_when_sending_then_it_is_in_nobody_s_summary():
    async def scenario(conn):
        farm, owner, _, _, visible, hidden = await _world(conn)
        await conn.execute("UPDATE parcels SET archived_at = now() WHERE id = ANY($1)", [visible, hidden])
        await send_daily_summary({}, _at(7), farm_id=farm)
        return (await _rows(conn, farm))[owner]["payload"]["items"]

    assert run(scenario) == []


def test_given_a_deleted_farm_when_sending_then_no_row_is_created():
    async def scenario(conn):
        farm, *_ = await _world(conn)
        await conn.execute("UPDATE farms SET deleted_at = now() WHERE id = $1", farm)
        return await send_daily_summary({}, _at(7), farm_id=farm), await conn.fetchval("SELECT count(*) FROM daily_summaries WHERE farm_id = $1", farm)

    assert run(scenario) == (0, 0)


def test_given_a_farm_id_when_sending_then_the_other_farms_are_not_touched():
    async def scenario(conn):
        farm, *_ = await _world(conn)
        other, *_ = await _world(conn)
        await send_daily_summary({}, _at(7), farm_id=farm)
        return await conn.fetchval("SELECT count(*) FROM daily_summaries WHERE farm_id = $1", other)

    assert run(scenario) == 0


def test_given_the_push_gateway_is_not_configured_when_sending_then_the_summary_is_stored_and_nothing_leaves():
    calls = []

    async def scenario(conn):
        farm, *_ = await _world(conn)
        await conn.execute("INSERT INTO notification_prefs (farm_id, user_id, summary_hour, alerts_enabled, push_token) SELECT $1, user_id, 7, true, 'tok' FROM farm_members WHERE farm_id = $1 AND role = 'owner'", farm)
        await send_daily_summary({"push": calls.append}, _at(7), farm_id=farm)
        return await conn.fetchval("SELECT count(*) FROM daily_summaries WHERE farm_id = $1", farm)

    assert run(scenario) == 3 and calls == []

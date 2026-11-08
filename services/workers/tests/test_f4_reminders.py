"""T054 (US2) - the morning reminder: one per active member, their visible irrigated parcels only, the payload is the minimal
worker-safe one, logged once per user and day, never for an archived parcel or a removed member."""
import uuid

from tasks.send_irrigation_reminders import send_irrigation_reminders
from tests._f3 import run, seed_parcel
from tests._f4_us import DAY, NOW, SpyPush, add_member, seed_world


def test_given_a_farm_then_each_active_member_is_reminded_for_their_visible_irrigated_parcels_only():
    async def scenario(conn):
        farm, mine = await seed_world(conn)
        other = await seed_parcel(conn, farm)
        rainfed = await seed_parcel(conn, farm)
        archived = await seed_parcel(conn, farm, archived=True)
        await conn.execute("UPDATE parcels SET irrigation='drip' WHERE id=ANY($1)", [other, archived])
        await conn.execute("UPDATE parcels SET irrigation='rainfed' WHERE id=$1", rainfed)
        owner, worker = await add_member(conn, farm, "owner"), await add_member(conn, farm, "worker")
        gone = await add_member(conn, farm, "worker", removed=True)
        await conn.execute("INSERT INTO worker_parcels (farm_id, user_id, parcel_id) VALUES ($1,$2,$3)", farm, worker, mine)
        out = await send_irrigation_reminders({"gateway": SpyPush()}, farm_id=farm, now=NOW)
        return out, dict(owner=owner, worker=worker, gone=gone, mine=mine, other=other, rainfed=rainfed, archived=archived)

    out, ids = run(scenario)
    by_user = {t["user_id"]: set(t["parcel_ids"]) for t in out["targets"]}
    assert by_user[str(ids["owner"])] == {str(ids["mine"]), str(ids["other"])}
    assert by_user[str(ids["worker"])] == {str(ids["mine"])}
    assert str(ids["gone"]) not in by_user


def test_given_a_push_token_then_one_minimal_notification_is_sent_per_user_and_day_and_logged_once():
    async def scenario(conn):
        farm, mine = await seed_world(conn)
        user = await add_member(conn, farm, "owner", token="tok-fixture")
        spy = SpyPush()
        await send_irrigation_reminders({"gateway": spy}, farm_id=farm, now=NOW)
        first = len(spy.sent)
        await send_irrigation_reminders({"gateway": spy}, farm_id=farm, now=NOW)  # replay of the same local day
        logged = await conn.fetchval("SELECT count(*) FROM irrigation_notification_log WHERE farm_id=$1 AND user_id=$2 AND for_date=$3", farm, user, DAY)
        return first, len(spy.sent), logged, spy.sent[0]

    first, total, logged, payload = run(scenario)
    assert (first, total, logged) == (1, 1, 1)
    assert set(payload) <= {"device_token", "alert_id", "locale"}  # nothing derived from the advice travels


def test_given_a_member_removed_after_the_first_run_then_the_next_run_no_longer_reminds_them():
    async def scenario(conn):
        farm, mine = await seed_world(conn)
        user = await add_member(conn, farm, "owner", token="tok-fixture")
        await send_irrigation_reminders({"gateway": SpyPush()}, farm_id=farm, now=NOW)
        await conn.execute("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", farm, user)
        spy = SpyPush()
        out = await send_irrigation_reminders({"gateway": spy}, farm_id=farm, now="2026-06-05T01:00:00+00:00")
        return user, out, spy.sent

    user, out, sent = run(scenario)
    assert str(user) not in {t["user_id"] for t in out["targets"]} and sent == []


def test_given_no_push_gateway_then_the_delivery_is_reported_unavailable_and_nothing_is_logged():
    async def scenario(conn):
        farm, mine = await seed_world(conn)
        user = await add_member(conn, farm, "owner", token="tok-fixture")

        class Off(SpyPush):
            def configured(self):
                return False

        out = await send_irrigation_reminders({"gateway": Off()}, farm_id=farm, now=NOW)
        return out, await conn.fetchval("SELECT count(*) FROM irrigation_notification_log WHERE farm_id=$1", farm)

    out, logged = run(scenario)
    assert out["delivery"] == {"availability": "unavailable", "reason": "gateway_not_configured"} and logged == 0

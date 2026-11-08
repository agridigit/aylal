"""T081 - R7-A1, R7-A2 on the running stack: the daily summary job writes one row per member at their hour, in their language and on their scope;
the API serves the same scope; the worker never learns about the hidden red parcel."""
import datetime as dt
import uuid

from tests.e2e._f3 import client, day, run_job, seed_forecast, setup_farm
from tests.helpers import sql
from tests.integration._f3 import seed_status

MOROCCO = dt.timezone(dt.timedelta(hours=1))


def _at(hour):
    return dt.datetime.combine(dt.date.today(), dt.time(hour, 5), tzinfo=MOROCCO).astimezone(dt.UTC)


def _world(c):
    s = setup_farm(c, 3, worker=True, hidden=1)
    farm = uuid.UUID(s["farm"])
    orange, green, red = (uuid.UUID(p) for p in s["parcels"])
    seed_status(farm, orange, "orange", rank=1)
    seed_status(farm, green, "green", rank=2)
    seed_status(farm, red, "red", rank=0)  # hidden from the worker
    seed_forecast(s["farm"], [day(0, icon="rain"), day(1)])
    sql("UPDATE users SET language = 'ary' WHERE id = $1", uuid.UUID(s["worker"]["user"]["id"]))
    return s, farm, red


def test_given_the_summary_hour_when_the_job_runs_then_each_member_gets_one_row_on_their_own_scope_and_language():
    with client() as c:
        s, farm, red = _world(c)
        assert run_job("send_daily_summary", now=_at(7), farm_id=farm) == 2  # owner + worker, at the default hour
        rows = {str(r["user_id"]): r for r in sql("SELECT user_id, locale, payload FROM daily_summaries WHERE farm_id = $1", farm)}
        worker = rows[s["worker"]["user"]["id"]]
        assert worker["locale"] == "ary" and str(red) not in str(worker["payload"])
        assert "rain" in str(worker["payload"])
        owner = next(r for k, r in rows.items() if k != s["worker"]["user"]["id"])
        assert str(red) in str(owner["payload"])
        assert run_job("send_daily_summary", now=_at(7), farm_id=farm) == 0


def test_given_a_stored_summary_when_each_member_reads_it_through_the_api_then_the_scope_matches_the_stored_row():
    with client() as c:
        s, farm, red = _world(c)
        run_job("send_daily_summary", now=_at(7), farm_id=farm)
        w = c.get(f"/farms/{s['farm']}/summary/today", headers=s["wh"])
        o = c.get(f"/farms/{s['farm']}/summary/today", headers=s["oh"])
        assert w.status_code == o.status_code == 200
        assert [i["color"] for i in o.json()["items"]] == ["red", "orange"] and [i["color"] for i in w.json()["items"]] == ["orange"]
        assert str(red) not in w.text and w.json()["locale"] == "ary"


def test_given_a_member_who_moves_the_hour_when_the_job_runs_then_the_summary_follows_the_chosen_hour_and_the_other_hours_send_nothing():
    with client() as c:
        s, farm, _ = _world(c)
        assert c.put(f"/farms/{s['farm']}/summary/settings", json={"summary_hour": 18, "alerts_enabled": True}, headers=s["oh"]).status_code == 200
        assert run_job("send_daily_summary", now=_at(7), farm_id=farm) == 1   # only the worker, still on the default hour
        assert run_job("send_daily_summary", now=_at(18), farm_id=farm) == 1  # only the owner


def test_given_a_removed_worker_when_the_job_runs_then_no_summary_is_created_for_them():
    with client() as c:
        s, farm, _ = _world(c)
        assert c.delete(f"/farms/{s['farm']}/members/{s['worker']['user']['id']}", headers=s["oh"]).status_code in (200, 204)
        run_job("send_daily_summary", now=_at(7), farm_id=farm)
        assert sql("SELECT count(*) FROM daily_summaries WHERE farm_id = $1 AND user_id = $2", farm, uuid.UUID(s["worker"]["user"]["id"]))[0][0] == 0

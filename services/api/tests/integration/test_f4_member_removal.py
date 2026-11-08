"""T022 - G1 (FR-021): active membership (removed_at IS NULL) is replayed on every read/generation; a removed member, a role change or a
deleted farm purges per-user data in the same transaction; events stay; the author is anonymised only when the ACCOUNT is deleted."""
import asyncio
import os
from pathlib import Path

import pytest
import yaml

from tests.helpers import auth, sql
from tests.integration._f4 import TODAY4, call, export_of, seed_analysis, seed_event, world4  # noqa: F401

INFRA = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "infra/powersync/sync-rules.yaml"


def _log(farm, user, day=TODAY4):
    sql("INSERT INTO irrigation_notification_log (farm_id, user_id, for_date, sent_at) VALUES ($1,$2,$3,now())", farm, user, day)


def _count(table, farm, user):
    return sql(f"SELECT count(*) FROM {table} WHERE farm_id=$1 AND user_id=$2", farm, user)[0][0]


def _params(bucket, user):
    q = yaml.safe_load(INFRA.read_text(encoding="utf-8"))["bucket_definitions"][bucket]["parameters"]
    return sql(q.replace("request.user_id()", f"'{user}'::uuid"))


def _targets(farm, day=TODAY4):
    from app.db.session import sessionmaker
    from app.irrigation.reminders import reminder_targets

    async def run():
        async with sessionmaker() as s:
            return await reminder_targets(s, farm, day)

    return asyncio.run(run())


def _setup(w):
    _log(w["farm_a"], w["worker"])
    _log(w["farm_a"], w["worker2"])
    seed_event(w["farm_a"], w["a1"], w["worker"])


def test_given_a_removed_member_then_buckets_log_and_reminders_stop_and_events_and_authors_stay(client, token_for, world4):
    w = world4
    _setup(w)
    tok = token_for(w["worker"])
    assert any(t["user_id"] == w["worker"] for t in _targets(w["farm_a"]))
    assert len(_params("farm_worker_irrigation_own", w["worker"])) == 3
    assert call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice").status_code == 200
    assert client.delete(f"/v1/farms/{w['farm_a']}/members/{w['worker']}", headers=auth(token_for(w["owner"]))).status_code == 204
    f = f"/v1/farms/{w['farm_a']}"
    assert _count("irrigation_notification_log", w["farm_a"], w["worker"]) == 0 and _count("irrigation_notification_log", w["farm_a"], w["worker2"]) == 1
    assert call(client, tok, "GET", f"{f}/irrigation/advice").status_code == 404
    assert call(client, tok, "GET", f"{f}/irrigation/consumption").status_code == 404
    assert not any(t["user_id"] == w["worker"] for t in _targets(w["farm_a"]))
    assert _params("farm_worker_irrigation_own", w["worker"]) == [] and _params("farm_worker_irrigation", w["worker"]) == []
    assert sql("SELECT count(*) FROM irrigation_events WHERE farm_id=$1 AND author_id=$2", w["farm_a"], w["worker"])[0][0] == 1  # events remain
    assert export_of(w["worker"])["irrigation"]["events"] == []


def test_given_a_member_removed_without_the_worker_parcels_purge_then_reminders_still_exclude_them(world4):
    """The active-membership predicate is replayed on every generation: stale worker_parcels rows never reach a removed member."""
    w = world4
    sql("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["worker"])
    assert any(t["user_id"] == w["worker2"] for t in _targets(w["farm_a"]))
    assert not any(t["user_id"] == w["worker"] for t in _targets(w["farm_a"]))
    sql("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["manager"])
    assert not any(t["user_id"] == w["manager"] for t in _targets(w["farm_a"]))
    assert _params("farm_irrigation", w["manager"]) == []


def test_given_a_role_change_then_the_per_user_data_of_the_member_is_purged(client, token_for, world4):
    w = world4
    _setup(w)
    r = client.patch(f"/v1/farms/{w['farm_a']}/members/{w['worker']}", headers=auth(token_for(w["owner"])), json={"role": "manager"})
    assert r.status_code == 200, r.text
    assert _count("irrigation_notification_log", w["farm_a"], w["worker"]) == 0 and _count("irrigation_notification_log", w["farm_a"], w["worker2"]) == 1
    assert sql("SELECT count(*) FROM irrigation_events WHERE author_id=$1", w["worker"])[0][0] == 1


def test_given_a_deleted_then_purged_farm_then_all_farm_irrigation_data_is_gone(client, token_for, world4):
    from app.db.session import sessionmaker
    from app.irrigation.lifecycle import purge_farm_irrigation

    w = world4
    _setup(w)
    seed_analysis(w["farm_a"], w["a1"], w["owner"])
    sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    assert call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice").status_code == 404

    async def run():
        async with sessionmaker() as s:
            await purge_farm_irrigation(s, w["farm_a"])
            await s.commit()

    asyncio.run(run())
    assert sql("SELECT count(*) FROM irrigation_notification_log WHERE farm_id=$1", w["farm_a"])[0][0] == 0
    assert sql("SELECT count(*) FROM irrigation_plans WHERE farm_id=$1", w["farm_a"])[0][0] == 0
    assert sql("SELECT count(*) FROM irrigation_events WHERE farm_id=$1", w["farm_b"])[0][0] == 0  # other farms are untouched (and had none)
    assert sql("SELECT count(*) FROM irrigation_plans WHERE farm_id=$1", w["farm_b"])[0][0] == 1


def test_given_the_removal_purge_then_it_runs_in_the_same_transaction_as_the_removal(client, token_for, world4):
    """If the purge fails, the member must stay in place: no half-removed state."""
    from app.irrigation import lifecycle

    w = world4
    _setup(w)
    original = lifecycle.purge_member_irrigation

    async def boom(*a, **k):
        raise RuntimeError("purge failed")

    lifecycle.purge_member_irrigation = boom
    try:
        with pytest.raises(Exception):
            client.delete(f"/v1/farms/{w['farm_a']}/members/{w['worker']}", headers=auth(token_for(w["owner"])))
    finally:
        lifecycle.purge_member_irrigation = original
    assert sql("SELECT removed_at FROM farm_members WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["worker"])[0][0] is None
    assert _count("irrigation_notification_log", w["farm_a"], w["worker"]) == 1


def test_given_the_account_deletion_function_then_the_author_and_note_are_anonymised_only_then(world4):
    w = world4
    ev = seed_event(w["farm_a"], w["a1"], w["worker"], note="private note")
    other = seed_event(w["farm_a"], w["a1"], w["owner"], note="owner note")
    an = seed_analysis(w["farm_a"], w["a1"], w["worker"])
    sql("UPDATE farm_members SET removed_at=now() WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["worker"])  # leaving the farm changes nothing
    assert sql("SELECT author_id, note FROM irrigation_events WHERE id=$1", ev)[0][:] == (w["worker"], "private note")
    sql("SELECT anonymize_registry_operator($1::uuid)", w["worker"])  # F6 maintenance function, extended by F4
    assert sql("SELECT author_id, note FROM irrigation_events WHERE id=$1", ev)[0][:] == (None, None)
    assert sql("SELECT author_id FROM water_analyses WHERE id=$1", an)[0][0] is None
    assert sql("SELECT author_id, note FROM irrigation_events WHERE id=$1", other)[0][:] == (w["owner"], "owner note")
    assert sql("SELECT count(*) FROM irrigation_notification_log WHERE user_id=$1", w["worker"])[0][0] == 0


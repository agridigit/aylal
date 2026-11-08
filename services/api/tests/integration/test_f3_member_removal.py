"""T027a - G1 (FR-021): a removed member, a role change or a deleted farm purges the member's summaries and preferences;
REST, sync and export agree; the user_summaries and worker buckets stop serving."""
import asyncio
import os
from pathlib import Path

import pytest
import yaml

from tests.helpers import auth, sql
from tests.integration._f3 import (  # noqa: F401
    call,
    seed_prefs,
    seed_summary,
    seed_worker_rows,
    sync_obs,
    sync_post,
    world3,
)

INFRA = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "infra/powersync/sync-rules.yaml"


def _count(table, farm, user):
    return sql(f"SELECT count(*) FROM {table} WHERE farm_id=$1 AND user_id=$2", farm, user)[0][0]


def _export(user):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, user)

    return asyncio.run(run())


def _summary_params(user):
    """Rows the user_summaries bucket parameter query yields for the user (request.user_id() bound to `user`)."""
    q = yaml.safe_load(INFRA.read_text(encoding="utf-8"))["bucket_definitions"]["user_summaries"]["parameters"]
    return sql(q.replace("request.user_id()", f"'{user}'::uuid"))


def _worker_params(user):
    q = yaml.safe_load(INFRA.read_text(encoding="utf-8"))["bucket_definitions"]["farm_worker_monitoring"]["parameters"]
    return sql(q.replace("request.user_id()", f"'{user}'::uuid"))


def _setup(w):
    seed_summary(w["farm_a"], w["worker"])
    seed_summary(w["farm_a"], w["worker2"])
    seed_prefs(w["farm_a"], w["worker"])
    seed_prefs(w["farm_a"], w["worker2"])


def _assert_before(client, token_for, w):
    tok = token_for(w["worker"])
    assert call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/summary/today").status_code == 200
    assert call(client, tok, "PUT", f"/v1/farms/{w['farm_a']}/summary/settings", {"summary_hour": 8, "alerts_enabled": True}).status_code == 200
    assert [r["user_id"] for r in _summary_params(w["worker"])] == [w["worker"]]
    assert len(_worker_params(w["worker"])) == 3
    assert any(s["farm_id"] == str(w["farm_a"]) for s in _export(w["worker"])["monitoring"]["daily_summaries"])


def _assert_after(client, token_for, w, tok):
    f = f"/v1/farms/{w['farm_a']}"
    assert _count("daily_summaries", w["farm_a"], w["worker"]) == 0 and _count("notification_prefs", w["farm_a"], w["worker"]) == 0
    assert call(client, tok, "GET", f"{f}/summary/today").status_code == 404
    assert call(client, tok, "PUT", f"{f}/summary/settings", {"summary_hour": 8, "alerts_enabled": True}).status_code == 404
    z = sql("SELECT id FROM attention_zones WHERE farm_id=$1 LIMIT 1", w["farm_a"])[0][0]
    assert sync_post(client, tok, [sync_obs(w["farm_a"], z)]).status_code == 404
    assert [s for s in _export(w["worker"])["monitoring"]["daily_summaries"] if s["farm_id"] == str(w["farm_a"])] == []
    assert _summary_params(w["worker"]) == []                       # the user_summaries bucket is no longer opened
    assert _count("daily_summaries", w["farm_a"], w["worker2"]) == 1  # another member's rows are untouched ...
    served = sql("SELECT user_id FROM daily_summaries WHERE farm_id=$1", w["farm_a"])
    assert [r["user_id"] for r in served] == [w["worker2"]]          # ... and never served to the removed member


def test_given_a_removed_member_then_summaries_and_preferences_are_purged_and_every_path_agrees(client, token_for, world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    _setup(w)
    _assert_before(client, token_for, w)
    tok = token_for(w["worker"])
    assert client.delete(f"/v1/farms/{w['farm_a']}/members/{w['worker']}", headers=auth(token_for(w["owner"]))).status_code == 204
    _assert_after(client, token_for, w, tok)
    assert _worker_params(w["worker"]) == []                        # worker_parcels purged -> farm_worker_monitoring is empty


def test_given_a_role_change_then_summaries_and_preferences_of_the_member_are_purged(client, token_for, world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    _setup(w)
    _assert_before(client, token_for, w)
    r = client.patch(f"/v1/farms/{w['farm_a']}/members/{w['worker']}", headers=auth(token_for(w["owner"])), json={"role": "manager"})
    assert r.status_code == 200, r.text
    assert _count("daily_summaries", w["farm_a"], w["worker"]) == 0 and _count("notification_prefs", w["farm_a"], w["worker"]) == 0
    assert _count("daily_summaries", w["farm_a"], w["worker2"]) == 1 and _count("notification_prefs", w["farm_a"], w["worker2"]) == 1
    assert _worker_params(w["worker"]) == []


def test_given_a_deleted_then_purged_farm_then_all_member_summaries_and_preferences_are_gone(client, token_for, world3):
    from app.db.session import sessionmaker
    from app.monitoring.lifecycle import purge_farm_monitoring

    w = world3
    _setup(w)
    _assert_before(client, token_for, w)
    sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    tok = token_for(w["worker"])
    f = f"/v1/farms/{w['farm_a']}"
    assert call(client, tok, "GET", f"{f}/summary/today").status_code == 404
    assert [s for s in _export(w["worker"])["monitoring"]["daily_summaries"] if s["farm_id"] == str(w["farm_a"])] == []

    async def run():
        async with sessionmaker() as s:
            await purge_farm_monitoring(s, w["farm_a"])
            await s.commit()

    asyncio.run(run())
    assert sql("SELECT count(*) FROM daily_summaries WHERE farm_id=$1", w["farm_a"])[0][0] == 0
    assert sql("SELECT count(*) FROM notification_prefs WHERE farm_id=$1", w["farm_a"])[0][0] == 0


def test_given_the_removal_purge_then_it_runs_in_the_same_transaction_as_the_removal(client, token_for, world3):
    """If the purge fails, the member must stay in place: no half-removed state."""
    from app.monitoring import lifecycle

    w = world3
    _setup(w)
    assert _count("daily_summaries", w["farm_a"], w["worker"]) == 1
    original = lifecycle.purge_member_monitoring

    async def boom(*a, **k):
        raise RuntimeError("purge failed")

    lifecycle.purge_member_monitoring = boom
    try:
        with pytest.raises(Exception):
            client.delete(f"/v1/farms/{w['farm_a']}/members/{w['worker']}", headers=auth(token_for(w["owner"])))
    finally:
        lifecycle.purge_member_monitoring = original
    assert sql("SELECT removed_at FROM farm_members WHERE farm_id=$1 AND user_id=$2", w["farm_a"], w["worker"])[0][0] is None
    assert _count("daily_summaries", w["farm_a"], w["worker"]) == 1

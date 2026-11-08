"""T021 - G1: an archived or invisible parcel is hidden EVERYWHERE through the single predicate visible_parcels(ctx)."""
import asyncio
import os
import re
from pathlib import Path

import yaml

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    TODAY4,
    call,
    export_of,
    seed_event,
    seed_f4_rows,
    sync_event,
    sync_post,
    world4,
)

APP = Path(__file__).resolve().parents[2] / "app"
REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))


def _archive(parcel):
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", parcel)


def test_given_the_f4_access_module_then_it_delegates_to_the_f3_predicate_and_exposes_visible_parcels():
    from app.irrigation import access
    from app.monitoring import access as f3

    assert callable(access.visible_parcels)
    text = (APP / "irrigation" / "access.py").read_text(encoding="utf-8")
    assert "app.monitoring.access" in text or "from app.monitoring" in text
    assert access.visible_parcels is f3.visible_parcels or "visible_parcels" in text


def test_given_an_archived_parcel_when_reading_through_rest_sync_and_the_list_then_a_worker_sees_nothing(client, token_for, world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    tok = token_for(w["worker"])
    f = f"/v1/farms/{w['farm_a']}"
    assert call(client, tok, "GET", f"{f}/parcels/{w['a1']}/irrigation/advice").status_code == 200
    assert str(w["a1"]) in {i["parcel_id"] for i in call(client, tok, "GET", f"{f}/irrigation/advice").json()["items"]}
    _archive(w["a1"])
    assert call(client, tok, "GET", f"{f}/parcels/{w['a1']}/irrigation/advice").status_code == 404
    assert call(client, tok, "GET", f"{f}/parcels/{w['a1']}/irrigation/events").status_code == 404
    assert str(w["a1"]) not in {i["parcel_id"] for i in call(client, tok, "GET", f"{f}/irrigation/advice").json()["items"]}
    assert sync_post(client, tok, [sync_event(w["farm_a"], w["a1"])]).status_code == 404
    assert str(w["a1"]) not in {p["parcel_id"] for p in call(client, tok, "GET", f"{f}/irrigation/consumption").json()["parcels"]}


def test_given_an_archived_parcel_then_the_denormalised_copy_is_set_and_cleared_by_the_trigger(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    tables = ("irrigation_systems", "irrigation_events", "irrigation_applied", "water_analyses", "water_balance_days", "irrigation_plans")
    for t in tables:
        assert sql(f"SELECT count(*) FROM {t} WHERE parcel_id=$1 AND parcel_archived_at IS NULL", w["a1"])[0][0] >= 1, t
    _archive(w["a1"])
    for t in tables:
        assert sql(f"SELECT count(*) FROM {t} WHERE parcel_id=$1 AND parcel_archived_at IS NULL", w["a1"])[0][0] == 0, t
    sql("UPDATE parcels SET archived_at=NULL WHERE id=$1", w["a1"])
    for t in tables:
        assert sql(f"SELECT count(*) FROM {t} WHERE parcel_id=$1 AND parcel_archived_at IS NOT NULL", w["a1"])[0][0] == 0, t


def test_given_an_archived_parcel_then_the_worker_export_drops_it_and_staff_keep_the_read_only_history(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    assert {e["parcel_id"] for e in export_of(w["worker"])["irrigation"]["events"]} == {str(w["a1"])}
    _archive(w["a1"])
    assert export_of(w["worker"])["irrigation"]["events"] == []
    assert str(w["a1"]) in {e["parcel_id"] for e in export_of(w["owner"])["irrigation"]["events"]}


def test_given_the_powersync_buckets_then_an_archived_parcel_leaves_every_worker_bucket(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    rules = yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
    for bucket in ("farm_worker_irrigation", "farm_worker_irrigation_own"):
        for q in rules[bucket]["data"]:
            q = q.replace("bucket.parcel_id", f"'{w['a1']}'::uuid").replace("bucket.user_id", f"'{w['worker']}'::uuid")
            assert sql(q), (bucket, q)
    _archive(w["a1"])
    for bucket in ("farm_worker_irrigation", "farm_worker_irrigation_own"):
        for q in rules[bucket]["data"]:
            q = q.replace("bucket.parcel_id", f"'{w['a1']}'::uuid").replace("bucket.user_id", f"'{w['worker']}'::uuid")
            assert sql(q) == [], (bucket, q)


def test_given_an_archived_parcel_then_no_plan_is_computed_and_no_reminder_is_sent(world4):
    from app.db.session import sessionmaker
    from app.irrigation.reminders import reminder_targets

    w = world4
    _archive(w["a1"])

    async def run():
        async with sessionmaker() as s:
            return [t["parcel_id"] for t in await reminder_targets(s, w["farm_a"], TODAY4)]

    assert w["a1"] not in asyncio.run(run())
    from app.irrigation.plans import parcels_to_compute

    async def compute():
        async with sessionmaker() as s:
            return await parcels_to_compute(s, w["farm_a"])

    assert w["a1"] not in asyncio.run(compute()) and w["p"][2] in asyncio.run(compute())


def test_given_the_f4_sources_then_every_sql_on_parcel_scoped_data_goes_through_the_predicate():
    files = sorted((APP / "irrigation").glob("*.py")) + [APP / "sync" / "irrigation.py"]
    files += [REPO / "services/workers/tasks" / f"{n}.py" for n in ("compute_irrigation_plans", "send_irrigation_reminders")]
    assert any(p.name == "access.py" for p in files)
    scoped = re.compile(r"\bFROM\s+(irrigation_events|irrigation_applied|irrigation_plans|water_analyses|water_balance_days|irrigation_systems)\b", re.I)
    for p in files:
        text = p.read_text(encoding="utf-8")
        if p.name in ("access.py", "lifecycle.py"):
            continue
        if scoped.search(text):
            assert re.search(r"visible_parcels|VISIBLE_PARCELS_SQL|parcel_archived_at\s+IS\s+NULL", text), f"{p.name}: F4 SQL without the visibility predicate"

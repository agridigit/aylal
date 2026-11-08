"""T020 - G1: every access path (REST, sync, export, advice list, consumption aggregate, reminder) gives the same verdict for the
same (role, farm, parcel) scenario; inventory tests fail when a route, table, sync rule or worker task is missing from the matrix."""
import asyncio
import os
import re
import uuid
from pathlib import Path

import pytest
import yaml

from tests.helpers import auth, sql
from tests.integration._f4 import TODAY4, call, export_of, seed_event, seed_plan, sync_event, sync_post, world4  # noqa: F401

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
COVERED_ROUTES = {
    "irrigation/advice", "irrigation/consumption", "parcels/{parcel_id}/irrigation-system", "parcels/{parcel_id}/irrigation-system/versions",
    "parcels/{parcel_id}/irrigation/advice", "parcels/{parcel_id}/irrigation/balance", "parcels/{parcel_id}/irrigation/events",
    "parcels/{parcel_id}/irrigation/events/{event_id}/cancel", "parcels/{parcel_id}/water-analyses",
}
COVERED_TABLES = {"irrigation_systems", "irrigation_system_versions", "irrigation_events", "irrigation_applied", "water_analyses", "water_balance_days",
                  "irrigation_plans", "moisture_corrections", "irrigation_notification_log", "weather_observed", "crop_irrigation_params", "soil_textures", "irrigation_params", "irrigation_jobs"}
COVERED_TASKS = {"compute_irrigation_plans", "import_irrigation_params", "send_irrigation_reminders"}
COVERED_BUCKETS = {"farm_irrigation", "farm_worker_irrigation", "farm_worker_irrigation_own", "irrigation_reference"}
# every task that existed before F4 (F1-F3 + F6 sets of test_f3_path_parity.py), so adding a task is never silently accepted
PRE_F4_TASKS = {"__init__", "build_registry_export", "build_tiles", "expire_invitations", "import_phyto_catalog", "mark_overdue_operations", "object_storage",
                "purge_archived_fields", "purge_deleted_accounts", "purge_expired_registry", "send_otp", "drain_backfill_jobs", "refresh_weather", "evaluate_alerts",
                "import_crop_thresholds", "recompute_status", "detect_zones", "send_daily_summary", "ingest_imagery", "backfill_parcel_vigor"}
F4_PATH = re.compile(r"^/v1/farms/\{farm_id\}/(irrigation|parcels/\{parcel_id\}/(irrigation|water-analyses))")


def test_given_the_live_api_then_every_f4_route_is_in_the_parity_matrix_and_vice_versa(client):
    live = {p.split("/v1/farms/{farm_id}/")[1] for p in client.get("/openapi.json").json()["paths"] if F4_PATH.match(p)}
    live |= {p.split("/v1/farms/{farm_id}/")[1] for p in client.get("/openapi.json").json()["paths"] if "irrigation-system" in p}
    assert live, "no F4 route is served"
    assert live == COVERED_ROUTES, live ^ COVERED_ROUTES


def test_given_the_database_then_every_f4_table_exists_and_is_in_the_matrix():
    found = {r[0] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = ANY($1)", sorted(COVERED_TABLES))}
    assert found == COVERED_TABLES, COVERED_TABLES - found
    live = {r[0] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE 'irrigation%' OR table_name LIKE 'water\\_%' ESCAPE '\\')")}
    assert live <= COVERED_TABLES, live - COVERED_TABLES


def test_given_the_worker_tasks_then_every_f4_task_exists_and_none_is_missing_from_the_matrix():
    present = {p.stem for p in (REPO / "services/workers/tasks").glob("*.py")} - PRE_F4_TASKS
    assert present == COVERED_TASKS, present ^ COVERED_TASKS


def test_given_the_sync_rules_then_every_f4_bucket_is_in_the_matrix():
    buckets = set(yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"])
    assert {b for b in buckets if "irrigation" in b} == COVERED_BUCKETS


def _reminded(user, farm):
    from app.db.session import sessionmaker
    from app.irrigation.reminders import reminder_targets

    async def run():
        async with sessionmaker() as s:
            return await reminder_targets(s, farm, TODAY4)

    return {str(t["parcel_id"]) for t in asyncio.run(run()) if t["user_id"] == user}


def _visible(role, farm_kind, parcel_kind):
    if farm_kind != "own":
        return None
    return parcel_kind == "assigned" or (role == "owner" and parcel_kind == "unassigned")


@pytest.mark.parametrize("role", ["worker", "owner"])
@pytest.mark.parametrize("farm_kind", ["own", "other", "unknown", "deleted"])
@pytest.mark.parametrize("parcel_kind", ["assigned", "unassigned", "archived", "unknown"])
def test_given_a_scenario_when_using_every_path_then_the_verdicts_are_identical(client, token_for, world4, role, farm_kind, parcel_kind):
    w = world4
    caller = w["worker"] if role == "worker" else w["owner"]
    tok = token_for(caller)
    assert call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice").status_code == 200  # precondition: routes exist
    parcel = {"assigned": w["a1"], "unassigned": w["hidden"], "archived": w["p"][1], "unknown": uuid.uuid4()}[parcel_kind]
    if parcel_kind != "unknown":
        seed_event(w["farm_a"], parcel, w["owner"])
    if parcel_kind == "archived":
        sql("UPDATE parcels SET archived_at=now() WHERE id=$1", parcel)
    farm = {"own": w["farm_a"], "other": w["farm_b"], "unknown": uuid.uuid4(), "deleted": w["farm_a"]}[farm_kind]
    if farm_kind == "deleted":
        sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    vis = _visible(role, farm_kind, parcel_kind)
    f = f"/v1/farms/{farm}"
    rest = call(client, tok, "GET", f"{f}/parcels/{parcel}/irrigation/advice").status_code
    sync = sync_post(client, tok, [sync_event(farm, parcel)]).status_code
    listed = call(client, tok, "GET", f"{f}/irrigation/advice")
    cons = call(client, tok, "GET", f"{f}/irrigation/consumption")
    in_list = None if listed.status_code == 404 else str(parcel) in {i["parcel_id"] for i in listed.json()["items"]}
    in_cons = None if cons.status_code == 404 else str(parcel) in {p["parcel_id"] for p in cons.json()["parcels"]}
    exported = str(parcel) in {p["parcel_id"] for p in export_of(caller)["irrigation"]["plans"]}
    reminded = str(parcel) in _reminded(caller, w["farm_a"]) if farm_kind == "own" else False
    if vis is None:
        assert (rest, sync, listed.status_code, cons.status_code) == (404, 404, 404, 404)
        if farm_kind == "deleted":
            assert not exported
        assert not reminded
    else:
        assert rest == (200 if vis else 404) and sync == (200 if vis else 404)
        assert in_list is vis and in_cons is vis
        assert reminded is vis  # archived or unassigned parcels are never reminded to anyone who cannot see them
        assert exported is (vis or (role == "owner" and parcel_kind == "archived"))  # staff keep archived history in the export

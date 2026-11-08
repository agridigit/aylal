"""T018 - G1: every access path (REST, sync upload, export, summary, aggregate) gives the same verdict for the same
(role, farm, parcel) scenario; an inventory test fails when a route, table or worker task is missing from the matrix."""
import asyncio
import os
import re
import uuid
from pathlib import Path

import pytest

from tests.helpers import auth, sql
from tests.integration._f3 import call, seed_alert, seed_zone, sync_obs, sync_post, world3  # noqa: F401

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
COVERED_ROUTES = {
    "dashboard", "weather", "alerts", "alerts/{alert_id}/dismiss", "parcels/{parcel_id}/status", "parcels/{parcel_id}/vigor",
    "parcels/{parcel_id}/vigor/compare", "parcels/{parcel_id}/vigor/scenes/{scene_id}/map", "parcels/{parcel_id}/vigor/reprocess",
    "zones", "zones/{zone_id}/dismiss", "zones/{zone_id}/observations/photo", "zones/{zone_id}/observations", "summary/today", "summary/settings",
}
COVERED_TABLES = {"farm_weather", "alerts", "parcel_status", "parcel_status_items", "parcel_vigor_points", "vigor_maps", "attention_zones",
                  "zone_observations", "observation_uploads", "daily_summaries", "notification_prefs", "monitoring_jobs"}
COVERED_TASKS = {"refresh_weather", "evaluate_alerts", "import_crop_thresholds", "recompute_status", "detect_zones", "send_daily_summary",
                 "ingest_imagery", "backfill_parcel_vigor"}
PRE_F3_TASKS = {"__init__", "build_registry_export", "build_tiles", "expire_invitations", "import_phyto_catalog", "mark_overdue_operations",
                "object_storage", "purge_archived_fields", "purge_deleted_accounts", "purge_expired_registry", "send_otp"}
F3_PATH = re.compile(r"^/v1/farms/\{farm_id\}/(dashboard|weather|alerts|zones|summary|parcels/\{parcel_id\}/(status|vigor))")


def test_given_the_live_api_then_every_f3_route_is_in_the_parity_matrix_and_vice_versa(client):
    live = {p.split("/v1/farms/{farm_id}/")[1] for p in client.get("/openapi.json").json()["paths"] if F3_PATH.match(p)}
    live = {re.sub(r"\{(alert|zone|scene)_id\}", lambda m: "{" + m.group(1) + "_id}", p) for p in live}
    assert live, "no F3 route is served"
    assert live == COVERED_ROUTES, (live ^ COVERED_ROUTES)


def test_given_the_database_then_every_f3_table_exists_and_is_in_the_matrix():
    found = {r[0] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = ANY($1)", sorted(COVERED_TABLES))}
    assert found == COVERED_TABLES, COVERED_TABLES - found


def test_given_the_worker_tasks_then_every_f3_task_exists_and_none_is_missing_from_the_matrix():
    present = {p.stem for p in (REPO / "services/workers/tasks").glob("*.py")} - PRE_F3_TASKS
    assert present == COVERED_TASKS, present ^ COVERED_TASKS


def _setup(w, role, farm_kind, parcel_kind):
    caller = w["worker"] if role == "worker" else w["owner"]
    parcel = {"assigned": w["a1"], "unassigned": w["hidden"], "archived": w["p"][1], "unknown": uuid.uuid4()}[parcel_kind]
    zone = seed_zone(w["farm_a"], parcel) if parcel_kind != "unknown" else uuid.uuid4()
    if parcel_kind != "unknown":
        seed_alert(w["farm_a"], parcel)
    if parcel_kind == "archived":
        sql("UPDATE parcels SET archived_at=now() WHERE id=$1", parcel)
    farm = {"own": w["farm_a"], "other": w["farm_b"], "unknown": uuid.uuid4(), "deleted": w["farm_a"]}[farm_kind]
    if farm_kind == "deleted":
        sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm_a"])
    return caller, farm, parcel, zone


def _visible(role, farm_kind, parcel_kind):
    if farm_kind != "own":
        return None
    return parcel_kind == "assigned" or (role == "owner" and parcel_kind == "unassigned")


def _export_alert_parcels(user):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, user)

    return {a["parcel_id"] for a in asyncio.run(run())["monitoring"]["alerts"]}


@pytest.mark.parametrize("role", ["worker", "owner"])
@pytest.mark.parametrize("farm_kind", ["own", "other", "unknown", "deleted"])
@pytest.mark.parametrize("parcel_kind", ["assigned", "unassigned", "archived", "unknown"])
def test_given_a_scenario_when_using_every_path_then_the_verdicts_are_identical(client, token_for, world3, role, farm_kind, parcel_kind):
    w = world3
    caller = w["worker"] if role == "worker" else w["owner"]
    tok = token_for(caller)
    assert client.get(f"/v1/farms/{w['farm_a']}/dashboard", headers=auth(tok)).status_code == 200  # precondition: routes exist
    caller, farm, parcel, zone = _setup(w, role, farm_kind, parcel_kind)
    vis = _visible(role, farm_kind, parcel_kind)
    f = f"/v1/farms/{farm}"
    rest = call(client, tok, "GET", f"{f}/parcels/{parcel}/status").status_code
    sync = sync_post(client, tok, [sync_obs(farm, zone)]).status_code
    summary = call(client, tok, "GET", f"{f}/summary/today")
    dash = call(client, tok, "GET", f"{f}/dashboard")
    in_summary = None if summary.status_code == 404 else str(parcel) in {i["parcel_id"] for i in summary.json()["items"]}
    in_dash = None if dash.status_code == 404 else str(parcel) in {p["parcel_id"] for p in dash.json()["parcels"]}
    exported = str(parcel) in _export_alert_parcels(caller)
    if vis is None:
        assert (rest, sync, summary.status_code, dash.status_code) == (404, 404, 404, 404)
        if farm_kind == "deleted":
            assert not exported  # a deleted farm leaves the export
    else:
        assert rest == (200 if vis else 404) and sync == (200 if vis else 404)
        assert in_summary is vis and in_dash is vis
        assert exported is (vis or (role == "owner" and parcel_kind == "archived"))  # staff keep archived history in the export

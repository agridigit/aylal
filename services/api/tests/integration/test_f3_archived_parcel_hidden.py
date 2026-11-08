"""T019 - G1: one predicate visible_parcels(ctx); an archived or unassigned parcel is hidden everywhere."""
import asyncio
import pathlib

from tests.helpers import sql
from tests.integration._f3 import NOT_FOUND, call, seed_alert, seed_worker_rows, world3  # noqa: F401

APP = pathlib.Path(__file__).resolve().parents[2] / "app"


def _ctx_ids(farm, user, role):
    from app.auth.farm_context import FarmContext
    from app.db.session import sessionmaker
    from app.monitoring.access import visible_parcels

    async def run():
        async with sessionmaker() as s:
            return set(await visible_parcels(FarmContext(farm, user, role, s)))

    return asyncio.run(run())


def test_given_the_predicate_then_a_worker_sees_assigned_active_parcels_and_staff_all_active_parcels(world3):
    w = world3
    assert _ctx_ids(w["farm_a"], w["worker"], "worker") == set(w["p"][:3])
    assert _ctx_ids(w["farm_a"], w["owner"], "owner") == set(w["p"])
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["p"][0])
    assert _ctx_ids(w["farm_a"], w["worker"], "worker") == set(w["p"][1:3])
    assert _ctx_ids(w["farm_a"], w["manager"], "manager") == set(w["p"][1:])


def test_given_the_code_then_every_path_calls_the_single_predicate():
    for rel in ("sync/monitoring.py", "monitoring/service.py", "accounts/export.py"):
        assert "visible_parcels" in (APP / rel).read_text(encoding="utf-8"), rel
    for rel in ("routers/dashboard.py", "routers/alerts.py", "routers/zones.py", "routers/vigor.py", "routers/summary.py"):
        text = (APP / rel).read_text(encoding="utf-8")
        assert "visible_parcels" in text or "monitoring.service" in text or "monitoring.access" in text, rel


def test_given_an_archived_parcel_when_a_worker_reads_rest_then_it_is_absent_everywhere(client, token_for, world3):
    w = world3
    rows = seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    tok = token_for(w["worker"])
    f = f"/v1/farms/{w['farm_a']}"
    before = call(client, tok, "GET", f"{f}/dashboard").json()
    assert str(w["a1"]) in {p["parcel_id"] for p in before["parcels"]}
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    after = call(client, tok, "GET", f"{f}/dashboard").json()
    assert str(w["a1"]) not in {p["parcel_id"] for p in after["parcels"]}
    assert after["counts"] == {"red": 0, "orange": 1, "green": 1}
    assert str(w["a1"]) not in {a["parcel_id"] for a in call(client, tok, "GET", f"{f}/alerts").json()}
    assert str(rows["zone"]) not in {z["id"] for z in call(client, tok, "GET", f"{f}/zones").json()}
    for path in (f"parcels/{w['a1']}/status", f"parcels/{w['a1']}/vigor", f"parcels/{w['a1']}/vigor/compare",
                 f"parcels/{w['a1']}/vigor/scenes/{rows['scene']}/map"):
        assert call(client, tok, "GET", f"{f}/{path}").json() == NOT_FOUND, path


def test_given_an_archived_parcel_when_staff_read_then_history_is_readable_but_absent_from_aggregates_and_alerts(client, token_for, world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    tok = token_for(w["owner"])
    f = f"/v1/farms/{w['farm_a']}"
    full = call(client, tok, "GET", f"{f}/dashboard").json()
    assert full["counts"] == {"red": 2, "orange": 2, "green": 6}
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    dash = call(client, tok, "GET", f"{f}/dashboard").json()
    assert str(w["a1"]) not in {p["parcel_id"] for p in dash["parcels"]}
    assert dash["counts"] == {"red": 1, "orange": 2, "green": 6}
    assert str(w["a1"]) not in {a["parcel_id"] for a in call(client, tok, "GET", f"{f}/alerts").json()}
    hist = call(client, tok, "GET", f"{f}/parcels/{w['a1']}/vigor")
    assert hist.status_code == 200 and hist.json()["points"], hist.text
    assert call(client, tok, "POST", f"{f}/parcels/{w['a1']}/vigor/reprocess").status_code == 404  # read-only history


def test_given_an_archived_parcel_then_the_trigger_copies_archived_at_and_back_on_restore_and_merge(world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    tables = ("alerts", "parcel_status", "parcel_status_items", "parcel_vigor_points", "vigor_maps", "attention_zones", "zone_observations")
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    for t in tables:
        assert sql(f"SELECT count(*) FROM {t} WHERE parcel_id=$1 AND parcel_archived_at IS NULL", w["a1"])[0][0] == 0, t
    sql("UPDATE parcels SET archived_at=NULL WHERE id=$1", w["a1"])
    for t in tables:
        assert sql(f"SELECT count(*) FROM {t} WHERE parcel_id=$1 AND parcel_archived_at IS NOT NULL", w["a1"])[0][0] == 0, t


def _alerts_in_export(user):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, user)

    return {a["parcel_id"] for a in asyncio.run(run())["monitoring"]["alerts"]}


def test_given_an_archived_parcel_then_the_worker_export_drops_it_and_the_staff_export_keeps_it(world3):
    w = world3
    seed_alert(w["farm_a"], w["a1"])
    assert str(w["a1"]) in _alerts_in_export(w["worker"]) and str(w["a1"]) in _alerts_in_export(w["owner"])
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    assert str(w["a1"]) not in _alerts_in_export(w["worker"])
    assert str(w["a1"]) in _alerts_in_export(w["owner"])


def test_given_notification_workers_then_recipients_and_per_recipient_parcels_come_from_visible_parcels(world3):
    import asyncio as aio

    from app.db.session import sessionmaker
    from app.monitoring.service import notification_recipients  # noqa: F401  (recipients and their parcels, via visible_parcels)

    w = world3

    async def run():
        async with sessionmaker() as s:
            return await notification_recipients(s, w["farm_a"])

    got = {u: set(ps) for u, ps in aio.run(run()).items()}
    assert got[w["worker"]] == set(w["p"][:3]) and got[w["owner"]] == set(w["p"]) and got[w["worker2"]] == set()
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    again = {u: set(ps) for u, ps in aio.run(run()).items()}
    assert again[w["worker"]] == set(w["p"][1:3]) and w["a1"] not in again[w["owner"]]


def test_given_the_shared_sql_predicate_then_access_py_builds_on_it_and_it_names_archived_and_worker_scope():
    from app.monitoring.access_sql import VISIBLE_PARCELS_SQL

    assert "archived_at IS NULL" in VISIBLE_PARCELS_SQL and "worker_parcels" in VISIBLE_PARCELS_SQL and ":farm" in VISIBLE_PARCELS_SQL
    assert "access_sql" in (APP / "monitoring" / "access.py").read_text(encoding="utf-8")

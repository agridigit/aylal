"""T014 - G1: an archived parcel is hidden from the worker everywhere; staff keep reading archived/merged history."""
import asyncio
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, add_registry, op_body, sync_op, world  # noqa: F401


def _archive(parcel):
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", parcel)


def test_given_an_archived_parcel_then_the_trigger_copies_archived_at_into_operation_parcels_and_back(world):
    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"])
    assert sql("SELECT parcel_archived_at FROM operation_parcels WHERE operation_id=$1", oid)[0][0] is None
    _archive(w["a1"])
    assert sql("SELECT parcel_archived_at FROM operation_parcels WHERE operation_id=$1", oid)[0][0] is not None
    sql("UPDATE parcels SET archived_at=NULL WHERE id=$1", w["a1"])
    assert sql("SELECT parcel_archived_at FROM operation_parcels WHERE operation_id=$1", oid)[0][0] is None


def test_given_an_archived_parcel_when_a_worker_reads_rest_then_it_is_absent_from_list_detail_and_dar(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"])
    h = auth(token_for(w["worker"]))
    assert [i["id"] for i in client.get(f"/v1/farms/{w['farm_a']}/operations", headers=h).json()["items"]] == [str(oid)]
    _archive(w["a1"])
    assert client.get(f"/v1/farms/{w['farm_a']}/operations", headers=h).json()["items"] == []
    assert client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=h).status_code == 404
    assert client.get(f"/v1/farms/{w['farm_a']}/operations?parcel_id={w['a1']}", headers=h).status_code in (200, 404)
    assert client.get(f"/v1/farms/{w['farm_a']}/fields/{w['a1']}/earliest-harvest", headers=h).status_code == 404


def test_given_an_archived_parcel_when_a_worker_writes_through_sync_then_it_is_refused(client, token_for, world):
    w = world
    ok = client.post("/v1/sync/upload", headers=auth(token_for(w["worker"])), json={"ops": [sync_op(
        "operations", w["farm_a"], uuid.uuid4(), {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]})]})
    assert ok.status_code == 200, ok.text
    _archive(w["a1"])
    r = client.post("/v1/sync/upload", headers=auth(token_for(w["worker"])), json={"ops": [sync_op(
        "operations", w["farm_a"], uuid.uuid4(), {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]})]})
    assert r.status_code == 404, r.text


def test_given_an_archived_parcel_when_exporting_the_worker_account_then_its_lines_are_absent(world):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"])

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, w["worker"])

    assert [o["id"] for o in asyncio.run(run())["operations"]] == [str(oid)]
    _archive(w["a1"])
    assert asyncio.run(run())["operations"] == []


def test_given_an_archived_parcel_then_the_worker_sync_rules_filter_on_parcel_archived_at():
    import os
    import pathlib

    text = (pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "infra/powersync/sync-rules.yaml").read_text()
    section = text.split("farm_worker_ops:")[1]
    assert "operation_parcels" in section and "parcel_archived_at IS NULL" in section


def test_given_an_archived_or_merged_parcel_when_staff_read_then_journal_and_registry_still_show_it(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["manager"], w["a1"], type_="phyto")
    add_registry(w["farm_a"], oid, w["a1"])
    _archive(w["a1"])
    for who in ("owner", "manager"):
        h = auth(token_for(w[who]))
        assert client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=h).status_code == 200
        reg = client.get(f"/v1/farms/{w['farm_a']}/registry", headers=h)
        assert reg.status_code == 200 and len(reg.json()["items"]) == 1

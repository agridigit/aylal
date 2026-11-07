"""T019 - G4: retention, anonymisation of the operator, purge after retain_until, registry in the account export."""
import asyncio
import datetime as dt

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, add_registry, world  # noqa: F401


def _export(user):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, user)
    return asyncio.run(run())


def test_given_a_deleted_operator_when_anonymising_then_entries_are_kept_with_no_personal_data(world):
    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"], type_="phyto")
    rid = add_registry(w["farm_a"], oid, w["a1"], operator_user=w["worker"], operator_name="Ahmed +212600000000")
    sql("SELECT anonymize_registry_operator($1::uuid)", w["worker"])
    row = sql("SELECT operator_name, operator_user_id FROM registry_entries WHERE id=$1", rid)[0]
    assert row["operator_user_id"] is None
    assert "212" not in row["operator_name"] and row["operator_name"] == "opérateur supprimé"


def test_given_a_direct_update_of_the_operator_then_it_is_refused_only_the_function_may_anonymise(world):
    import pytest
    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"])
    rid = add_registry(w["farm_a"], oid, w["a1"], operator_user=w["worker"])
    with pytest.raises(Exception, match="registry_append_only"):
        sql("UPDATE registry_entries SET operator_user_id = NULL WHERE id=$1", rid)


def test_given_entries_before_and_after_retain_until_when_purging_then_only_expired_rows_go(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    old = add_registry(w["farm_a"], oid, w["a1"], performed_on=TODAY - dt.timedelta(days=2000), retain_until=TODAY - dt.timedelta(days=1))
    keep = add_registry(w["farm_a"], oid, w["a1"], retain_until=TODAY + dt.timedelta(days=1))
    sql("SELECT purge_expired_registry($1::date)", TODAY)
    ids = {r[0] for r in sql("SELECT id FROM registry_entries WHERE farm_id=$1", w["farm_a"])}
    assert keep in ids and old not in ids


def test_given_nothing_expired_when_purging_then_nothing_is_deleted(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    add_registry(w["farm_a"], oid, w["a1"], retain_until=TODAY)
    sql("SELECT purge_expired_registry($1::date)", TODAY - dt.timedelta(days=1))
    assert sql("SELECT count(*) FROM registry_entries WHERE farm_id=$1", w["farm_a"])[0][0] == 1


def test_given_the_worker_task_then_it_exists_and_calls_the_purge_function():
    import os
    import pathlib

    p = pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "services/workers/tasks/purge_expired_registry.py"
    assert p.exists() and "purge_expired_registry" in p.read_text()


def test_given_the_account_export_then_the_registry_is_included_for_staff(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    add_registry(w["farm_a"], oid, w["a1"], operator_user=w["owner"])
    data = _export(w["owner"])
    assert "registry" in data and len(data["registry"]) == 1


def test_given_a_sole_owner_deleting_the_account_then_the_registry_is_exported_first_and_kept(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    add_registry(w["farm_a"], oid, w["a1"], operator_user=w["owner"])
    r = client.post("/v1/me/deletion", headers=auth(token_for(w["owner"])), json={})
    assert r.status_code in (200, 202), r.text
    assert r.json().get("registry_export_id"), "the registry must be exported to the requester before anonymisation"
    assert sql("SELECT count(*) FROM registry_entries WHERE farm_id=$1", w["farm_a"])[0][0] == 1

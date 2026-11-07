"""Anonymisation scope: deleting an AUTHOR must not erase the identity of a distinct, still existing OPERATOR (regulatory register)."""
import contextlib
import datetime as dt
import uuid

import asyncpg
import pytest

from tests.integration.test_f6_anonymise_account_data import _register
from tests.integration.test_sql_account_repo import _cleanup, _insert_user, _user, run

TODAY = dt.date.today()
GONE_NAME = "opérateur supprimé"
REG_COLS = "product_name, dose, dose_unit, performed_on, parcel_id, parcel_name, crop_name, area_ha, allocated_quantity, retain_until"
OP_COLS = "free_product_name, dose, dose_unit, performed_on, type, status"


async def _world(conn):
    gone, g = _user(uuid.uuid4().int % 10**7, display_name="Gone")
    keeper, k = _user(uuid.uuid4().int % 10**7, display_name="Keeper")
    w = dict(gone=gone, keeper=keeper, farm=uuid.uuid4(), parcel=uuid.uuid4(),
             op_by_gone=uuid.uuid4(), op_for_gone=uuid.uuid4(), op_other=uuid.uuid4())
    await _insert_user(conn, g)
    await _insert_user(conn, k)
    await conn.execute("INSERT INTO farms (id,name,owner_id) VALUES ($1,'F',$2)", w["farm"], keeper)
    await conn.execute("INSERT INTO farm_members (farm_id,user_id,role) VALUES ($1,$2,'owner'),($1,$3,'manager')", w["farm"], keeper, gone)
    await conn.execute("INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES ($1,$2,'P1',"
        "ST_SetSRID(ST_GeomFromText('POLYGON((-7.5 33.5,-7.49 33.5,-7.49 33.51,-7.5 33.51,-7.5 33.5))'),4326),0.5)", w["parcel"], w["farm"])
    # (op, author, operator user, operator name, note)
    for oid, author, operator, name, note in (
        (w["op_by_gone"], gone, keeper, "Karim Keeper", "note ecrite par Gone"),
        (w["op_for_gone"], keeper, gone, "Ahmed Gone 0612345678", "note ecrite par Keeper"),
        (w["op_other"], keeper, keeper, "Karim Keeper", "note sans lien"),
    ):
        await conn.execute(
            "INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, operator_user_id, operator_name, note,"
            " free_product_name, dose, dose_unit) VALUES ($1,$2,'phyto',$3,'validated',$4,$5,$6,$7,'Prod X',2,'L/ha')",
            oid, w["farm"], TODAY, author, operator, name, note)
    for key, oid, recorder, operator, name in (
        ("r_by_gone", w["op_by_gone"], gone, keeper, "Karim Keeper"),
        ("r_for_gone", w["op_for_gone"], keeper, gone, "Ahmed Gone 0612345678"),
        ("r_other", w["op_other"], keeper, keeper, "Karim Keeper"),
    ):
        names, marks, vals, rid = _register(conn, w["farm"], oid, w["parcel"], recorded_by=recorder, operator_user_id=operator, operator_name=name)
        await conn.execute(f"INSERT INTO registry_entries ({names}) VALUES ({marks})", *vals)
        w[key] = rid
    for key, oid, author, field, before, after in (
        ("c_by_gone", w["op_by_gone"], gone, "note", '"ancienne note Gone"', '"note ecrite par Gone"'),
        ("c_dose_by_gone", w["op_by_gone"], gone, "dose", "2", "3"),
        ("c_by_keeper", w["op_for_gone"], keeper, "note", '"avant Keeper"', '"note ecrite par Keeper"'),
    ):
        cid = uuid.uuid4()
        await conn.execute(
            "INSERT INTO operation_corrections (id, farm_id, operation_id, field, before, after, author_id, source)"
            " VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,'manual')", cid, w["farm"], oid, field, before, after, author)
        w[key] = cid
    w["regulatory"] = {k: await conn.fetchrow(f"SELECT {REG_COLS} FROM registry_entries WHERE id=$1", w[k]) for k in ("r_by_gone", "r_for_gone", "r_other")}
    w["op_regulatory"] = {k: await conn.fetchrow(f"SELECT {OP_COLS} FROM operations WHERE id=$1", w[k]) for k in ("op_by_gone", "op_for_gone", "op_other")}
    return w


async def _teardown(conn, w):
    with contextlib.suppress(Exception):  # the append-only guard keeps registry/correction rows: best effort on unique test data
        await conn.execute("SELECT set_config('aylal.registry_maintenance','on',false)")
        await conn.execute("DELETE FROM farm_members WHERE farm_id=$1", w["farm"])
        await conn.execute("DELETE FROM farms WHERE id=$1", w["farm"])
        await _cleanup(conn, [w["gone"], w["keeper"]])


def _scenario(check):
    async def go(conn):
        w = await _world(conn)
        try:
            await conn.fetch("SELECT anonymize_registry_operator($1::uuid)", w["gone"])
            await check(conn, w)
        finally:
            await _teardown(conn, w)

    run(go)


def test_given_a_deleted_author_when_anonymising_then_the_existing_operator_identity_is_unchanged_but_author_and_note_are_erased():
    async def check(conn, w):
        op = await conn.fetchrow("SELECT author_id, operator_user_id, operator_name, note FROM operations WHERE id=$1", w["op_by_gone"])
        assert op["operator_user_id"] == w["keeper"] and op["operator_name"] == "Karim Keeper"
        assert op["author_id"] is None and op["note"] is None
        reg = await conn.fetchrow("SELECT recorded_by, operator_user_id, operator_name FROM registry_entries WHERE id=$1", w["r_by_gone"])
        assert reg["operator_user_id"] == w["keeper"] and reg["operator_name"] == "Karim Keeper"
        assert reg["recorded_by"] is None
        corr = await conn.fetchrow("SELECT author_id, before, after FROM operation_corrections WHERE id=$1", w["c_by_gone"])
        assert corr["author_id"] is None and corr["before"] is None and corr["after"] is None

    _scenario(check)


def test_given_a_deleted_operator_when_anonymising_then_operator_is_anonymised_but_the_author_note_and_recorder_are_kept():
    async def check(conn, w):
        op = await conn.fetchrow("SELECT author_id, operator_user_id, operator_name, note FROM operations WHERE id=$1", w["op_for_gone"])
        assert op["operator_user_id"] is None and op["operator_name"] == GONE_NAME
        assert op["author_id"] == w["keeper"] and op["note"] == "note ecrite par Keeper"
        reg = await conn.fetchrow("SELECT recorded_by, operator_user_id, operator_name FROM registry_entries WHERE id=$1", w["r_for_gone"])
        assert reg["operator_user_id"] is None and reg["operator_name"] == GONE_NAME and reg["recorded_by"] == w["keeper"]
        corr = await conn.fetchrow("SELECT author_id, before::text AS b, after::text AS a FROM operation_corrections WHERE id=$1", w["c_by_keeper"])
        assert corr["author_id"] == w["keeper"] and corr["b"] == '"avant Keeper"' and corr["a"] == '"note ecrite par Keeper"'

    _scenario(check)


def test_given_an_operation_unrelated_to_the_deleted_account_when_anonymising_then_it_is_unchanged():
    async def check(conn, w):
        op = await conn.fetchrow("SELECT author_id, operator_user_id, operator_name, note FROM operations WHERE id=$1", w["op_other"])
        assert (op["author_id"], op["operator_user_id"], op["operator_name"], op["note"]) == (w["keeper"], w["keeper"], "Karim Keeper", "note sans lien")
        reg = await conn.fetchrow("SELECT recorded_by, operator_user_id, operator_name FROM registry_entries WHERE id=$1", w["r_other"])
        assert (reg["recorded_by"], reg["operator_user_id"], reg["operator_name"]) == (w["keeper"], w["keeper"], "Karim Keeper")

    _scenario(check)


def test_given_any_anonymisation_then_regulatory_content_is_kept_in_every_case():
    async def check(conn, w):
        for k, before in w["regulatory"].items():
            assert await conn.fetchrow(f"SELECT {REG_COLS} FROM registry_entries WHERE id=$1", w[k]) == before
        for k, before in w["op_regulatory"].items():
            assert await conn.fetchrow(f"SELECT {OP_COLS} FROM operations WHERE id=$1", w[k]) == before
        dose = await conn.fetchrow("SELECT field, before::text AS b, after::text AS a FROM operation_corrections WHERE id=$1", w["c_dose_by_gone"])
        assert (dose["b"], dose["a"]) == ("2", "3")

    _scenario(check)


def test_given_the_maintenance_exemption_then_it_stays_narrow_for_other_columns_and_other_roles():
    async def go(conn):
        w = await _world(conn)
        try:
            # direct UPDATE (no maintenance flag) of the identity or of the author columns is refused
            for stmt in ("UPDATE registry_entries SET operator_user_id = NULL WHERE id=$1",
                         "UPDATE registry_entries SET recorded_by = recorded_by WHERE id=$1",
                         "UPDATE operation_corrections SET author_id = author_id WHERE id=$1"):
                target = w["c_by_gone"] if "operation_corrections" in stmt else w["r_by_gone"]
                with pytest.raises(asyncpg.PostgresError, match="registry_append_only"):
                    await conn.execute(stmt, target)
            # even with the maintenance flag on, a regulatory column (or a regulatory column next to recorded_by) is refused
            for stmt in ("UPDATE registry_entries SET product_name = 'X' WHERE id=$1",
                         "UPDATE registry_entries SET dose = 99 WHERE id=$1",
                         "UPDATE registry_entries SET retain_until = retain_until - 1 WHERE id=$1",
                         "UPDATE registry_entries SET recorded_by = NULL, product_name = 'X' WHERE id=$1"):
                tx = conn.transaction()
                await tx.start()
                try:
                    await conn.execute("SELECT set_config('aylal.registry_maintenance','on',true)")
                    with pytest.raises(asyncpg.PostgresError, match="registry_append_only"):
                        await conn.execute(stmt, w["r_by_gone"])
                finally:
                    await tx.rollback()
            tx = conn.transaction()
            await tx.start()
            try:
                await conn.execute("SELECT set_config('aylal.registry_maintenance','on',true)")
                with pytest.raises(asyncpg.PostgresError, match="registry_append_only"):
                    await conn.execute("UPDATE operation_corrections SET field = 'dose' WHERE id=$1", w["c_by_gone"])
            finally:
                await tx.rollback()
            # another role cannot run the anonymisation function
            try:
                await conn.execute("CREATE ROLE aylal_scope_probe NOLOGIN")
            except asyncpg.PostgresError:
                pytest.skip("cannot create a probe role")
            try:
                await conn.execute("SET ROLE aylal_scope_probe")
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await conn.fetch("SELECT anonymize_registry_operator($1::uuid)", w["gone"])
            finally:
                await conn.execute("RESET ROLE")
                await conn.execute("DROP ROLE aylal_scope_probe")
        finally:
            await _teardown(conn, w)

    run(go)

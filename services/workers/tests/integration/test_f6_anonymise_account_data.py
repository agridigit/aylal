"""T031d - hardening: purging a deleted account anonymises every F6 row tied to the user; regulatory content is kept."""
import contextlib
import datetime as dt
import uuid

from tests.integration.test_sql_account_repo import DSN, NOW, _cleanup, _insert_user, _user, run

from tasks.purge_deleted_accounts import SqlAccountRepo

PII = "Ahmed 0612345678"


def _register(conn, farm, op, parcel, **cols):
    base = dict(id=uuid.uuid4(), farm_id=farm, operation_id=op, parcel_id=parcel, entry_kind="application",
                performed_on=dt.date.today(), parcel_name="P1", crop_name="Tomate", area_ha=1, product_name="Prod X",
                is_free_product=False, dose=2, dose_unit="L/ha", allocated_quantity=2, operator_name=PII,
                operator_user_id=None, warnings="[]", recorded_by=uuid.uuid4(),
                retain_until=dt.date.today() + dt.timedelta(days=1800))
    base.update(cols)
    names = ", ".join(base)
    marks = ", ".join(f"${i + 1}" + ("::jsonb" if k == "warnings" else "") for i, k in enumerate(base))
    return names, marks, list(base.values()), base["id"]


def test_given_a_purged_account_then_operator_and_note_identifiers_are_removed_everywhere_and_regulatory_content_is_kept():
    async def scenario(conn):
        gone, g = _user(uuid.uuid4().int % 10**7, status="deletion_requested", deletion_requested_at=NOW - dt.timedelta(days=31), display_name="Gone")
        keeper, k = _user(uuid.uuid4().int % 10**7, display_name="Keeper")
        farm, parcel = uuid.uuid4(), uuid.uuid4()
        op_author, op_operator, op_other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        try:
            await _insert_user(conn, g)
            await _insert_user(conn, k)
            await conn.execute("INSERT INTO farms (id,name,owner_id) VALUES ($1,'F',$2)", farm, keeper)
            await conn.execute("INSERT INTO farm_members (farm_id,user_id,role) VALUES ($1,$2,'owner'),($1,$3,'worker')", farm, keeper, gone)
            await conn.execute("INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES ($1,$2,'P1',"
                "ST_SetSRID(ST_GeomFromText('POLYGON((-7.5 33.5,-7.49 33.5,-7.49 33.51,-7.5 33.51,-7.5 33.5))'),4326),0.5)", parcel, farm)
            for oid, author, operator, name, note in (
                (op_author, gone, None, "Karim", "appelle 0612345678"),
                (op_operator, keeper, gone, PII, "note operateur"),
                (op_other, keeper, None, "Karim", "note de karim"),
            ):
                await conn.execute(
                    "INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, operator_user_id, operator_name, note,"
                    " free_product_name, dose, dose_unit) VALUES ($1,$2,'phyto',$3,'validated',$4,$5,$6,$7,'Prod X',2,'L/ha')",
                    oid, farm, dt.date.today(), author, operator, name, note)
            names, marks, vals, by_recorder = _register(conn, farm, op_author, parcel, recorded_by=gone, operator_name="Karim")
            await conn.execute(f"INSERT INTO registry_entries ({names}) VALUES ({marks})", *vals)
            names, marks, vals, by_operator = _register(conn, farm, op_operator, parcel, operator_user_id=gone, recorded_by=keeper)
            await conn.execute(f"INSERT INTO registry_entries ({names}) VALUES ({marks})", *vals)
            names, marks, vals, other = _register(conn, farm, op_other, parcel, operator_name="Karim", recorded_by=keeper)
            await conn.execute(f"INSERT INTO registry_entries ({names}) VALUES ({marks})", *vals)
            for field, before, after in (("note", '"appelle 0612345678"', '"rappel Ahmed"'), ("operator_name", f'"{PII}"', '"Ahmed"'), ("dose", "2", "3")):
                await conn.execute(
                    "INSERT INTO operation_corrections (id, farm_id, operation_id, field, before, after, author_id, source)"
                    " VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,'manual')", uuid.uuid4(), farm, op_author, field, before, after, gone)

            await SqlAccountRepo(DSN).purge_deleted_accounts(NOW)

            assert await conn.fetchval("SELECT count(*) FROM users WHERE id=$1", gone) == 0
            # scope: only the deleted account's OWN identity goes (operator role -> name/id; author role -> author/recorder/note)
            row = await conn.fetchrow("SELECT operator_name, operator_user_id, recorded_by, product_name, dose, dose_unit FROM registry_entries WHERE id=$1", by_recorder)
            assert row["recorded_by"] is None and row["operator_name"] == "Karim"  # free-text third-party operator is kept
            assert row["product_name"] == "Prod X" and float(row["dose"]) == 2 and row["dose_unit"] == "L/ha"
            row = await conn.fetchrow("SELECT operator_name, operator_user_id, recorded_by, product_name, dose, dose_unit FROM registry_entries WHERE id=$1", by_operator)
            assert "0612" not in row["operator_name"] and "Ahmed" not in row["operator_name"] and row["operator_user_id"] is None
            assert row["recorded_by"] == keeper and row["product_name"] == "Prod X" and float(row["dose"]) == 2
            assert await conn.fetchval("SELECT operator_name FROM registry_entries WHERE id=$1", other) == "Karim"
            row = await conn.fetchrow("SELECT operator_name, note, author_id, free_product_name, dose, performed_on FROM operations WHERE id=$1", op_author)
            assert row["note"] is None and row["author_id"] is None and row["operator_name"] == "Karim"
            row = await conn.fetchrow("SELECT operator_name, note, operator_user_id, author_id, free_product_name, dose, performed_on FROM operations WHERE id=$1", op_operator)
            assert row["operator_user_id"] is None and "Ahmed" not in (row["operator_name"] or "")
            assert row["note"] == "note operateur" and row["author_id"] == keeper  # the author's note is not the deleted operator's
            for oid in (op_author, op_operator):
                row = await conn.fetchrow("SELECT free_product_name, dose, performed_on FROM operations WHERE id=$1", oid)
                assert row["free_product_name"] == "Prod X" and float(row["dose"]) == 2 and row["performed_on"] == dt.date.today()
            kept = await conn.fetchrow("SELECT operator_name, note FROM operations WHERE id=$1", op_other)
            assert (kept["operator_name"], kept["note"]) == ("Karim", "note de karim")
            # corrections authored by the user: identifier-bearing values scrubbed, the dose change kept
            rows = {r["field"]: r for r in await conn.fetch("SELECT field, before::text AS b, after::text AS a FROM operation_corrections WHERE operation_id=$1", op_author)}
            for f in ("note", "operator_name"):
                assert "0612" not in (rows[f]["b"] or "") and "Ahmed" not in (rows[f]["b"] or "") + (rows[f]["a"] or "")
            assert (rows["dose"]["b"], rows["dose"]["a"]) == ("2", "3")
        finally:  # best effort: the append-only guard keeps registry/correction rows, hence their farm (test data, unique ids)
            with contextlib.suppress(Exception):
                await conn.execute("SELECT set_config('aylal.registry_maintenance','on',false)")
                await conn.execute("DELETE FROM farm_members WHERE farm_id=$1", farm)
                await conn.execute("DELETE FROM farms WHERE id=$1", farm)
                await _cleanup(conn, [gone, keeper])

    run(scenario)

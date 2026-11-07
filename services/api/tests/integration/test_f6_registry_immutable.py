"""T018 - G4: the registry is append-only; corrections are compensating entries; the snapshot is frozen."""
import datetime as dt
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, add_registry, op_body, world  # noqa: F401


def _phyto(client, token_for, w, **kw):
    body = op_body([w["a1"]], type="phyto", free_product_name="Maison", dose=2, dose_unit="L/ha", **kw)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=body)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


def test_given_a_registry_row_when_updating_or_deleting_by_sql_then_registry_append_only(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    rid = add_registry(w["farm_a"], oid, w["a1"])
    for stmt in ("UPDATE registry_entries SET dose = 99 WHERE id = $1", "DELETE FROM registry_entries WHERE id = $1"):
        with pytest.raises(Exception, match="registry_append_only"):
            sql(stmt, rid)


def test_given_a_correction_row_when_updating_or_deleting_by_sql_then_registry_append_only(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    cid = uuid.uuid4()
    sql("INSERT INTO operation_corrections (id, farm_id, operation_id, field, before, after, author_id, source) "
        "VALUES ($1,$2,$3,'note','\"a\"','\"b\"',$4,'manual')", cid, w["farm_a"], oid, w["owner"])
    for stmt in ("UPDATE operation_corrections SET field='x' WHERE id=$1", "DELETE FROM operation_corrections WHERE id=$1"):
        with pytest.raises(Exception, match="registry_append_only"):
            sql(stmt, cid)


def test_given_the_application_role_then_it_has_no_update_or_delete_privilege_on_the_registry(world):
    rows = sql("SELECT privilege_type FROM information_schema.role_table_grants WHERE table_name IN "
               "('registry_entries','operation_corrections') AND grantee = current_user "
               "AND privilege_type IN ('UPDATE','DELETE')")
    assert sql("SELECT count(*) FROM information_schema.tables WHERE table_name='registry_entries'")[0][0] == 1
    assert rows == []


def test_given_the_api_then_no_route_modifies_or_deletes_the_registry(client):
    paths = client.get("/openapi.json").json()["paths"]
    reg = {p: i for p, i in paths.items() if "/registry" in p}
    assert reg, "registry routes not served"
    assert all(not ({"put", "patch", "delete"} & set(i)) for i in reg.values())


def test_given_a_done_phyto_treatment_then_one_application_entry_with_a_frozen_snapshot_and_retention(client, token_for, world):
    w = world
    oid = _phyto(client, token_for, w)
    row = sql("SELECT * FROM registry_entries WHERE operation_id=$1", oid)
    assert len(row) == 1 and row[0]["entry_kind"] == "application"
    e = row[0]
    assert e["parcel_name"] == "A1" and e["is_free_product"] is True and e["product_name"] == "Maison"
    assert float(e["dose"]) == 2 and e["dose_unit"] == "L/ha"
    assert (e["retain_until"].year, e["retain_until"].month) == (TODAY.year + 5, TODAY.month)


def test_given_a_correction_then_a_reversal_then_a_corrected_application_are_inserted_and_the_view_shows_only_the_latter(client, token_for, world):
    w = world
    oid = _phyto(client, token_for, w)
    r = client.patch(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(token_for(w["owner"])), json={"dose": 3})
    assert r.status_code == 200, r.text
    kinds = [x[0] for x in sql("SELECT entry_kind FROM registry_entries WHERE operation_id=$1 ORDER BY recorded_at, id", oid)]
    assert kinds == ["application", "reversal", "application"]
    current = sql("SELECT dose FROM registry_current WHERE operation_id=$1", oid)
    assert [float(x[0]) for x in current] == [3.0]
    corr = sql("SELECT field, before, after, author_id, corrected_at FROM operation_corrections WHERE operation_id=$1", oid)
    assert len(corr) >= 1 and corr[0]["author_id"] == w["owner"] and corr[0]["corrected_at"] is not None


def test_given_a_cancellation_then_a_single_reversal_is_inserted_and_the_view_is_empty(client, token_for, world):
    w = world
    oid = _phyto(client, token_for, w)
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/cancel", headers=auth(token_for(w["owner"]))).status_code == 200
    kinds = [x[0] for x in sql("SELECT entry_kind FROM registry_entries WHERE operation_id=$1 ORDER BY recorded_at, id", oid)]
    assert kinds == ["application", "reversal"]
    assert sql("SELECT count(*) FROM registry_current WHERE operation_id=$1", oid)[0][0] == 0
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == "cancelled"


def test_given_a_parcel_purge_or_catalog_update_then_the_registry_snapshot_is_unchanged(client, token_for, world):
    w = world
    oid = _phyto(client, token_for, w)
    before = sql("SELECT parcel_name, crop_name, area_ha, product_name, dose, dose_unit, operator_name, warnings, catalog_version_id "
                 "FROM registry_entries WHERE operation_id=$1", oid)[0]
    sql("UPDATE parcels SET name='Renamed' WHERE id=$1", w["a1"])
    sql("DELETE FROM worker_parcels WHERE parcel_id=$1", w["a1"])
    sql("UPDATE parcels SET archived_at=now(), purge_after=now() WHERE id=$1", w["a1"])
    after = sql("SELECT parcel_name, crop_name, area_ha, product_name, dose, dose_unit, operator_name, warnings, catalog_version_id "
                "FROM registry_entries WHERE operation_id=$1", oid)[0]
    assert dict(before) == dict(after) and after["parcel_name"] == "A1"

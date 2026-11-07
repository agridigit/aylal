"""T021 - reversible migration 0006_operations_journal (tables, composite FKs, CHECKs, partial unique index, triggers)."""
import datetime as dt
import subprocess
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f6 import add_operation, world  # noqa: F401

NEW = {"phyto_products", "phyto_product_uses", "catalog_versions", "operations", "operation_parcels", "operation_reminders",
       "registry_entries", "operation_corrections", "label_uploads", "export_jobs"}


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["alembic", *args], capture_output=True, text=True, cwd="/app")


def _tables() -> set[str]:
    return {r[0] for r in sql("SELECT tablename FROM pg_tables WHERE schemaname='public'")}


@pytest.fixture
def at_0005(migrated):
    r = _alembic("downgrade", "0005")
    assert r.returncode == 0, r.stdout + r.stderr
    yield
    _alembic("upgrade", "head")


def test_given_0005_when_upgrading_to_0006_then_the_f6_tables_exist(at_0005):
    r = _alembic("upgrade", "0006")
    assert r.returncode == 0, r.stdout + r.stderr
    assert NEW <= _tables()


def test_given_0006_when_downgrading_then_f6_is_gone_and_f0_to_f2_remain(at_0005):
    assert _alembic("upgrade", "0006").returncode == 0
    assert _alembic("downgrade", "0005").returncode == 0
    assert not (NEW & _tables())
    assert {"farms", "parcels", "worker_parcels", "users", "crops", "seasons", "field_blocks"} <= _tables()


def test_given_0006_up_down_up_when_cycling_then_it_is_idempotent(at_0005):
    for step in (("upgrade", "0006"), ("downgrade", "0005"), ("upgrade", "0006")):
        r = _alembic(*step)
        assert r.returncode == 0, r.stdout + r.stderr


def test_given_head_then_farm_tables_have_composite_foreign_keys(migrated):
    defs = " ".join(r[0] for r in sql(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
        "WHERE c.contype='f' AND t.relname IN ('operation_parcels','operation_reminders','operation_corrections')"))
    assert "(farm_id, parcel_id)" in defs and "(farm_id, operation_id)" in defs


def test_given_a_product_and_a_free_name_together_then_the_check_refuses(world):
    w = world
    pid = uuid.uuid4()
    sql("INSERT INTO catalog_versions (id, imported_at, source_date, row_count, checksum) VALUES (gen_random_uuid(), now(), current_date, 0, 'x')")
    sql("INSERT INTO phyto_products (id, name, name_normalized, active_ingredients, catalog_version_id) "
        "SELECT $1, 'P', 'p', '[]'::jsonb, id FROM catalog_versions LIMIT 1", pid)
    with pytest.raises(Exception, match="check"):
        sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, product_id, free_product_name) "
            "VALUES ($1,$2,'phyto',current_date,'validated',$3,$4,'X')", uuid.uuid4(), w["farm_a"], w["owner"], pid)


@pytest.mark.parametrize("day", ["1999-12-31", (dt.date.today() + dt.timedelta(days=366 * 3)).isoformat()])
def test_given_a_performed_on_out_of_bounds_then_the_check_refuses(world, day):
    w = world
    with pytest.raises(Exception, match="check"):
        sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) VALUES ($1,$2,'irrigation',$3,'validated',$4)",
            uuid.uuid4(), w["farm_a"], dt.date.fromisoformat(day), w["owner"])


def test_given_a_label_photo_key_with_a_forged_pattern_then_the_check_refuses(world):
    w = world
    good = f"farms/{w['farm_a']}/labels/{uuid.uuid4()}"
    sql("INSERT INTO label_uploads (id, farm_id, user_id, object_key) VALUES ($1,$2,$3,$4)", uuid.uuid4(), w["farm_a"], w["owner"], good)
    for bad in ("../x", f"farms/{w['farm_b']}/labels/{uuid.uuid4()}x/y/z", "http://evil/x", "labels/abc"):
        with pytest.raises(Exception, match="check"):
            sql("INSERT INTO label_uploads (id, farm_id, user_id, object_key) VALUES ($1,$2,$3,$4)", uuid.uuid4(), w["farm_a"], w["owner"], bad)
    with pytest.raises(Exception, match="check"):
        sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, label_photo_key) "
            "VALUES ($1,$2,'phyto',current_date,'validated',$3,'../etc/passwd')", uuid.uuid4(), w["farm_a"], w["owner"])


def test_given_two_active_export_jobs_for_one_farm_then_the_partial_unique_index_refuses(world):
    w = world
    ins = ("INSERT INTO export_jobs (id, farm_id, requested_by, scope, period_from, period_to, format, lang, state, row_count, expires_at) "
           "VALUES ($1,$2,$3,'farm','2026-01-01','2026-12-31','pdf','fr',$4,0,now()+interval '1 day')")
    sql(ins, uuid.uuid4(), w["farm_a"], w["owner"], "queued")
    sql(ins, uuid.uuid4(), w["farm_a"], w["owner"], "done")
    sql(ins, uuid.uuid4(), w["farm_b"], w["owner_b"], "queued")
    with pytest.raises(Exception, match="unique"):
        sql(ins, uuid.uuid4(), w["farm_a"], w["owner"], "running")


def test_given_head_then_append_only_triggers_exist_on_the_registry_tables(migrated):
    trig = {(r[0], r[1]) for r in sql("SELECT event_object_table, event_manipulation FROM information_schema.triggers "
                                      "WHERE event_object_table IN ('registry_entries','operation_corrections')")}
    for t in ("registry_entries", "operation_corrections"):
        assert (t, "UPDATE") in trig and (t, "DELETE") in trig


def test_given_archive_restore_and_merge_then_parcel_archived_at_is_copied_to_operation_parcels(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    q = "SELECT parcel_archived_at FROM operation_parcels WHERE operation_id=$1"
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    assert sql(q, oid)[0][0] is not None
    sql("UPDATE parcels SET archived_at=NULL WHERE id=$1", w["a1"])
    assert sql(q, oid)[0][0] is None
    sql("UPDATE parcels SET archived_at=now(), merged_into=$2 WHERE id=$1", w["a1"], w["a2"])
    assert sql(q, oid)[0][0] is not None


def test_given_head_then_f0_to_f2_data_is_untouched(migrated):
    assert sql("SELECT count(*) FROM crops WHERE farm_id IS NULL")[0][0] == 16

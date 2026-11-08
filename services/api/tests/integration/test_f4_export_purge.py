"""T031 - G1: F4 tables are in the personal-data export and the purge; migration shape (composite FKs, triggers, CHECK, GRANT, empty referentials)."""
import glob
import json
import re
from pathlib import Path

import pytest

from tests.helpers import sql
from tests.integration._f4 import export_of, seed_analysis, seed_event, seed_f4_rows, world4  # noqa: F401

APP = Path(__file__).resolve().parents[2] / "app"
EXPORT_KEYS = {"systems", "system_versions", "events", "analyses", "plans", "balance_days"}
TABLES = ("irrigation_systems", "irrigation_system_versions", "irrigation_events", "irrigation_applied", "water_analyses", "water_balance_days",
          "irrigation_plans", "moisture_corrections", "irrigation_notification_log")


def test_given_an_owner_then_the_export_carries_every_f4_section(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    sql("INSERT INTO irrigation_system_versions (id, farm_id, system_id, parcel_id, snapshot, changed_by, changed_at)"
        " SELECT gen_random_uuid(), farm_id, id, parcel_id, '{}'::jsonb, $2, now() FROM irrigation_systems WHERE parcel_id=$1", w["a1"], w["owner"])
    m = export_of(w["owner"])["irrigation"]
    assert EXPORT_KEYS <= set(m)
    assert len(m["systems"]) == 10 and len(m["plans"]) == 10 and len(m["events"]) == 1 and len(m["analyses"]) == 1 and len(m["system_versions"]) == 1 and len(m["balance_days"]) == 1


def test_given_a_worker_then_the_export_has_only_their_events_on_visible_parcels_and_no_analysis_and_no_plan_secret(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    seed_event(w["farm_a"], w["a1"], w["owner"])      # another author
    seed_event(w["farm_a"], w["hidden"], w["worker"])  # parcel not assigned
    m = export_of(w["worker"])["irrigation"]
    assert [e["author_id"] for e in m["events"]] == [str(w["worker"])] and {e["parcel_id"] for e in m["events"]} == {str(w["a1"])}
    assert m.get("analyses", []) == []
    text = json.dumps(m)
    for forbidden in ("ece_ds_m", "water_source", "leaching_fraction", "taw_mm", "raw_mm", "moisture_source", '"assumptions"', "well-42"):
        assert forbidden not in text, forbidden


def test_given_a_farm_deletion_then_every_f4_row_goes_by_cascade_without_an_explicit_delete_on_protected_tables(world4):
    w = world4
    seed_f4_rows(w["farm_a"], w["a1"], w["worker"])
    sql("DELETE FROM farms WHERE id=$1", w["farm_a"])  # the ON DELETE CASCADE chain is the purge
    for t in TABLES:
        assert sql(f"SELECT count(*) FROM {t} WHERE farm_id=$1", w["farm_a"])[0][0] == 0, t
    assert sql("SELECT count(*) FROM irrigation_plans WHERE farm_id=$1", w["farm_b"])[0][0] == 1


def test_given_the_purge_module_then_it_never_deletes_explicitly_from_protected_tables():
    text = (APP / "accounts" / "purge.py").read_text(encoding="utf-8") + (APP / "irrigation" / "lifecycle.py").read_text(encoding="utf-8")
    assert not re.search(r"DELETE\s+FROM\s+(operations|registry_entries|irrigation_events|water_analyses)\b", text, re.I)


def _migration():
    found = sorted(glob.glob(str(APP.parent / "alembic" / "versions" / "*_irrigation_water_balance.py")))
    assert found, "irrigation_water_balance migration missing"
    return Path(found[0]).read_text(encoding="utf-8")


def test_given_the_migration_then_composite_foreign_keys_triggers_checks_and_grants_exist():
    text = _migration()
    assert text.count("FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id)") >= 7
    assert "parcel_archived_at" in text and "CREATE TRIGGER" in text and "irrigation_applied" in text
    assert re.search(r"CHECK", text) and "GRANT" in text
    assert "worker_assumptions" in text


def test_given_the_migrated_database_then_no_referential_row_exists_but_test_fixtures_and_composite_fks_are_enforced(world4):
    import asyncpg

    for t in ("crop_irrigation_params", "soil_textures", "irrigation_params"):
        assert sql(f"SELECT count(*) FROM {t} WHERE validated_by IS DISTINCT FROM 'fixture'")[0][0] == 0, t
    w = world4
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        sql("INSERT INTO water_balance_days (id, farm_id, parcel_id, day) VALUES (gen_random_uuid(),$1,$2,current_date)", w["farm_a"], w["b1"])


def test_given_an_event_then_the_applied_row_is_fed_by_trigger_without_author_or_note_and_cancel_removes_it(world4):
    w = world4
    ev = seed_event(w["farm_a"], w["a1"], w["worker"], volume=12.0, net_mm=2.0)
    cols = {r[0] for r in sql("SELECT column_name FROM information_schema.columns WHERE table_name='irrigation_applied'")}
    assert not ({"author_id", "note"} & cols)
    assert sql("SELECT volume_m3 FROM irrigation_applied WHERE id=$1", ev)[0][0] == 12
    sql("UPDATE irrigation_events SET status='cancelled' WHERE id=$1", ev)
    assert sql("SELECT count(*) FROM irrigation_applied WHERE id=$1", ev)[0][0] == 0
    with pytest.raises(Exception):
        sql("UPDATE irrigation_events SET status='done' WHERE id=$1", ev)  # cancelled -> done is never allowed


def test_given_a_water_analysis_with_an_out_of_range_conductivity_then_the_database_refuses_it(world4):
    import asyncpg

    w = world4
    assert seed_analysis(w["farm_a"], w["a1"], w["owner"])
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        seed_analysis(w["farm_a"], w["a1"], w["owner"], ec=100.5)

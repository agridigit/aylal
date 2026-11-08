"""T027 - reversible migration 0010_dashboard_monitoring: tables, composite FKs, CHECKs, generated column, triggers, fixtures only."""
import subprocess
import uuid

import asyncpg
import pytest

from tests.helpers import sql
from tests.integration._f3 import seed_scene, seed_status, seed_zone, world3  # noqa: F401

PER_FARM = {"farm_weather", "alerts", "parcel_status", "parcel_status_items", "parcel_vigor_points", "vigor_maps", "attention_zones",
            "zone_observations", "observation_uploads", "daily_summaries", "notification_prefs", "monitoring_jobs"}
GLOBAL = {"crop_weather_thresholds", "monitoring_params", "imagery_tiles", "imagery_scenes", "weather_cells"}


def _alembic(*args):
    return subprocess.run(["alembic", *args], capture_output=True, text=True, cwd="/app")


def _tables():
    return {r[0] for r in sql("SELECT tablename FROM pg_tables WHERE schemaname='public'")}


@pytest.fixture
def at_0009(migrated):
    r = _alembic("downgrade", "0009")
    assert r.returncode == 0, r.stdout + r.stderr
    yield
    _alembic("upgrade", "head")


def test_given_0009_when_upgrading_to_0010_then_the_f3_tables_exist_and_downgrade_removes_them(at_0009):
    assert not ((PER_FARM | GLOBAL) & _tables())
    r = _alembic("upgrade", "0010")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (PER_FARM | GLOBAL) <= _tables()
    assert _alembic("downgrade", "0009").returncode == 0
    assert not ((PER_FARM | GLOBAL) & _tables())


def test_given_the_head_then_every_per_farm_table_has_farm_id_not_null_and_a_composite_parcel_foreign_key():
    for t in sorted(PER_FARM - {"farm_weather", "daily_summaries", "notification_prefs", "observation_uploads"}):
        col = sql("SELECT is_nullable FROM information_schema.columns WHERE table_name=$1 AND column_name='farm_id'", t)
        assert col and col[0][0] == "NO", t
        fks = sql("SELECT pg_get_constraintdef(c.oid) AS d FROM pg_constraint c WHERE c.conrelid = $1::regclass AND c.contype='f'", t)
        assert any("(farm_id, parcel_id)" in r["d"] and "parcels" in r["d"] for r in fks), f"{t}: no composite (farm_id, parcel_id) FK"


def test_given_a_vigor_point_then_valid_is_a_generated_column_following_the_80_percent_rule(world3):
    w = world3
    ins = ("INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct, reliability)"
           " VALUES (gen_random_uuid(),$1,$2,$3,current_date - $4::int,0.5,0.5,$5,'ok')")
    for i, (pct, expected) in enumerate(((79.9, False), (80.0, True))):
        scene, _ = seed_scene(w["farm_a"], w["p"][3 + i])
        sql("DELETE FROM parcel_vigor_points WHERE scene_id=$1", scene)
        sql(ins, w["farm_a"], w["p"][3 + i], scene, 40 + i, pct)
        assert sql("SELECT valid FROM parcel_vigor_points WHERE scene_id=$1", scene)[0][0] is expected
    with pytest.raises(asyncpg.exceptions.GeneratedAlwaysError):
        sql("UPDATE parcel_vigor_points SET valid = true")
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        sql(ins, w["farm_a"], w["p"][5], seed_scene(w["farm_a"], w["p"][5])[0], 50, 101)


def test_given_a_vigor_point_twice_for_one_parcel_and_scene_then_the_unique_key_refuses(world3):
    w = world3
    scene, _ = seed_scene(w["farm_a"], w["p"][3])
    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        sql("INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct, reliability)"
            " VALUES (gen_random_uuid(),$1,$2,$3,current_date,0.5,0.5,90,'ok')", w["farm_a"], w["p"][3], scene)


def test_given_a_map_key_outside_the_documented_pattern_then_the_check_refuses(world3):
    w = world3
    scene, _ = seed_scene(w["farm_a"], w["p"][3])
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        sql("INSERT INTO vigor_maps (id, farm_id, parcel_id, scene_id, acquired_on, map_key, bounds) VALUES (gen_random_uuid(),$1,$2,$3,current_date,'../etc/passwd','{}'::jsonb)",
            w["farm_a"], w["p"][3], scene)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        sql("INSERT INTO vigor_maps (id, farm_id, parcel_id, scene_id, acquired_on, map_key, bounds) VALUES (gen_random_uuid(),$1,$2,$3,current_date,$4,'{}'::jsonb)",
            w["farm_a"], w["p"][3], scene, f"farms/{w['farm_b']}/vigor/{uuid.uuid4()}.png")  # key of another farm


def test_given_the_seed_thresholds_then_every_row_is_marked_fixture_and_never_a_production_value():
    rows = sql("SELECT source FROM crop_weather_thresholds")
    assert rows == [] or {r[0] for r in rows} == {"fixture"}
    assert sql("SELECT count(*) FROM crop_weather_thresholds WHERE validated_by IS NOT NULL AND source <> 'fixture'")[0][0] == 0
    params = {r["key"] for r in sql("SELECT key FROM monitoring_params")}
    assert {"cloud_min_clear_pct", "min_area_ha", "frost_notify_hour", "summary_hour", "weather_stale_hours"} <= params

"""T010 - reversible migration 0004_fields_crops (PostGIS, GiST, composite FKs, partial unique index, CHECKs, seed)."""
import subprocess
import uuid

import pytest

from tests.helpers import sql

NEW = {"crops", "seasons", "field_blocks", "field_commands"}
SLUGS = {"olive", "citrus", "durum-wheat", "soft-wheat", "barley", "tomato", "potato", "onion", "berries", "avocado",
         "date-palm", "almond", "grape", "sugar-beet", "alfalfa", "silage-maize"}
SQUARE = "ST_SetSRID(ST_GeomFromText('POLYGON((-7.6 33.57,-7.599 33.57,-7.599 33.571,-7.6 33.571,-7.6 33.57))'), 4326)"


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["alembic", *args], capture_output=True, text=True, cwd="/app")


def _tables() -> set[str]:
    return {r[0] for r in sql("SELECT tablename FROM pg_tables WHERE schemaname='public'")}


@pytest.fixture
def at_0003(migrated):
    r = _alembic("downgrade", "0003")
    assert r.returncode == 0, r.stdout + r.stderr
    yield
    _alembic("upgrade", "head")


def test_given_0003_when_upgrading_to_0004_then_the_f2_tables_exist(at_0003):
    r = _alembic("upgrade", "0004")
    assert r.returncode == 0, r.stdout + r.stderr
    assert NEW <= _tables()


def test_given_0004_when_downgrading_then_the_f2_tables_are_gone_and_f1_remains(at_0003):
    assert _alembic("upgrade", "0004").returncode == 0
    assert _alembic("downgrade", "0003").returncode == 0
    assert not (NEW & _tables())
    assert {"farms", "parcels", "worker_parcels", "users"} <= _tables()


def test_given_0004_up_down_up_when_cycling_then_it_is_idempotent(at_0003):
    for step in (("upgrade", "0004"), ("downgrade", "0003"), ("upgrade", "0004")):
        r = _alembic(*step)
        assert r.returncode == 0, r.stdout + r.stderr


def test_given_head_then_postgis_is_installed_and_parcels_geometry_has_a_gist_index(migrated):
    assert sql("SELECT 1 FROM pg_extension WHERE extname='postgis'")
    defs = " ".join(r[0] for r in sql("SELECT indexdef FROM pg_indexes WHERE tablename='parcels'"))
    assert "gist" in defs.lower() and "geometry" in defs
    blocks = " ".join(r[0] for r in sql("SELECT indexdef FROM pg_indexes WHERE tablename='field_blocks'"))
    assert "gist" in blocks.lower()


def test_given_head_then_parcels_vigor_is_nullable_and_f2_columns_exist(migrated):
    cols = {r[0]: r[1] for r in sql(
        "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name='parcels'")}
    assert cols["vigor"] == "YES"
    assert {"area_calc_ha", "area_declared_ha", "irrigation", "greenhouse", "soil", "source", "gps_accuracy_m",
            "status_summary", "created_by", "archived_at", "purge_after", "merged_into_id"} <= set(cols)


def test_given_head_then_child_tables_reference_parcels_through_composite_fks_with_farm_id(migrated):
    for table, ref in (("seasons", "parcels"), ("field_blocks", "parcels")):
        defs = [r[0] for r in sql(
            "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
            "WHERE t.relname=$1 AND c.contype='f'", table)]
        assert any("(farm_id, field_id)" in d and f"REFERENCES {ref}(farm_id, id)" in d for d in defs), defs
    merged = [r[0] for r in sql(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
        "WHERE t.relname='parcels' AND c.contype='f'")]
    assert any("(farm_id, merged_into_id)" in d for d in merged), merged


def test_given_head_then_a_partial_unique_index_allows_one_active_season_per_field_and_crop(migrated):
    defs = " ".join(r[0] for r in sql("SELECT indexdef FROM pg_indexes WHERE tablename='seasons'"))
    assert "UNIQUE" in defs and "(field_id, crop_id)" in defs and "ended_at IS NULL" in defs


def _farm_with_field(make_farm):
    farm = make_farm({uuid.uuid4(): "owner"})
    field = uuid.uuid4()
    sql(f"INSERT INTO parcels (id, farm_id, name, geometry) VALUES ($1,$2,'P',{SQUARE})", field, farm)
    return farm, field


def _crop():
    return sql("SELECT id FROM crops WHERE farm_id IS NULL ORDER BY slug LIMIT 1")[0][0]


def test_given_an_active_season_when_starting_the_same_crop_again_then_the_database_refuses(make_farm):
    farm, field = _farm_with_field(make_farm)
    crop = _crop()
    q = "INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at) VALUES ($1,$2,$3,$4,current_date)"
    sql(q, uuid.uuid4(), farm, field, crop)
    with pytest.raises(Exception, match="unique|duplicate"):
        sql(q, uuid.uuid4(), farm, field, crop)


def test_given_a_closed_season_when_starting_the_same_crop_again_then_it_is_allowed(make_farm):
    farm, field = _farm_with_field(make_farm)
    crop = _crop()
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, ended_at) "
        "VALUES ($1,$2,$3,$4,'2025-01-01','2025-06-01')", uuid.uuid4(), farm, field, crop)
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at) VALUES ($1,$2,$3,$4,current_date)",
        uuid.uuid4(), farm, field, crop)


def test_given_a_season_with_both_planting_year_and_sowing_date_then_the_check_refuses_it(make_farm):
    farm, field = _farm_with_field(make_farm)
    with pytest.raises(Exception, match="check"):
        sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, planting_year, sowing_date) "
            "VALUES ($1,$2,$3,$4,current_date,2020,'2026-03-01')", uuid.uuid4(), farm, field, _crop())


def test_given_a_planting_year_out_of_range_then_the_check_refuses_it(make_farm):
    farm, field = _farm_with_field(make_farm)
    with pytest.raises(Exception, match="check"):
        sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, planting_year) "
            "VALUES ($1,$2,$3,$4,current_date,1850)", uuid.uuid4(), farm, field, _crop())


def test_given_a_season_pointing_to_a_field_of_another_farm_then_the_composite_fk_refuses_it(make_farm):
    farm_a, _ = _farm_with_field(make_farm)
    _, field_b = _farm_with_field(make_farm)
    with pytest.raises(Exception, match="foreign key"):
        sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at) VALUES ($1,$2,$3,$4,current_date)",
            uuid.uuid4(), farm_a, field_b, _crop())


def test_given_a_season_ending_before_it_starts_then_the_check_refuses_it(make_farm):
    farm, field = _farm_with_field(make_farm)
    with pytest.raises(Exception, match="check"):
        sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, ended_at) "
            "VALUES ($1,$2,$3,$4,'2026-05-01','2026-04-01')", uuid.uuid4(), farm, field, _crop())


def test_given_head_then_the_16_reference_crops_are_seeded_with_stages_for_those_with_agronomy(migrated):
    rows = sql("SELECT slug, cycle, has_agronomy, validated FROM crops WHERE farm_id IS NULL AND slug NOT LIKE 'fx\\_%'")
    assert {r[0] for r in rows} == SLUGS and len(rows) == 16
    assert {r[1] for r in rows} == {"perennial", "annual"}
    assert all(r[3] is False or r[3] is True for r in rows)


def test_given_a_crop_without_farm_when_reinserting_the_same_slug_then_it_is_refused(migrated):
    with pytest.raises(Exception, match="unique|duplicate"):
        sql("INSERT INTO crops (id, farm_id, slug, name_ary, name_ar, name_fr, cycle) "
            "VALUES ($1, NULL, 'olive', 'x', 'x', 'x', 'perennial')", uuid.uuid4())

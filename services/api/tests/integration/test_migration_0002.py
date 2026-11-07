"""T010 - reversible migration 0002_account_farm (up/down, single owner index, composite FKs)."""
import subprocess
import uuid

import pytest

from tests.helpers import sql


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["alembic", *args], capture_output=True, text=True, cwd="/app")


@pytest.fixture
def at_0001(migrated):
    r = _alembic("downgrade", "0001")
    assert r.returncode == 0, r.stdout + r.stderr
    yield
    _alembic("upgrade", "head")


def _tables() -> set[str]:
    return {r[0] for r in sql("SELECT tablename FROM pg_tables WHERE schemaname='public'")}


NEW = {"users", "consents", "otp_challenges", "refresh_tokens", "worker_parcels", "invitations",
       "geo_regions", "geo_provinces", "geo_communes"}


def test_given_head_when_upgrading_then_all_f1_tables_exist(at_0001):
    r = _alembic("upgrade", "0002")
    assert r.returncode == 0, r.stdout + r.stderr
    assert NEW <= _tables()


def test_given_0002_when_downgrading_then_f1_tables_are_gone_and_f0_remains(at_0001):
    assert _alembic("upgrade", "0002").returncode == 0
    assert _alembic("downgrade", "0001").returncode == 0
    assert not (NEW & _tables())
    assert {"farms", "farm_members", "parcels", "trial_records"} <= _tables()


def test_given_f0_roles_when_upgrading_then_editor_becomes_manager_and_viewer_becomes_worker(at_0001):
    farm, e, v = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    sql("INSERT INTO farms (id, name) VALUES ($1, 'F')", farm)
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1,$2,'editor'), ($1,$3,'viewer')", farm, e, v)
    assert _alembic("upgrade", "0002").returncode == 0
    roles = {str(r[0]): r[1] for r in sql("SELECT user_id, role FROM farm_members WHERE farm_id=$1", farm)}
    assert roles == {str(e): "manager", str(v): "worker"}


def test_given_0002_when_reading_indexes_then_a_partial_unique_index_allows_one_owner_per_farm(migrated):
    rows = sql("SELECT indexdef FROM pg_indexes WHERE tablename='farm_members'")
    defs = " ".join(r[0] for r in rows)
    assert "UNIQUE" in defs and "farm_id" in defs and "role = 'owner'" in defs
    assert any("user_id" in r[0] and "UNIQUE" not in r[0] for r in rows)


def test_given_0002_when_reading_worker_parcels_then_composite_fks_target_members_and_parcels(migrated):
    rows = sql(
        "SELECT confrelid::regclass::text, array_length(conkey, 1) FROM pg_constraint"
        " WHERE conrelid = 'worker_parcels'::regclass AND contype = 'f'"
    )
    assert {(r[0], r[1]) for r in rows} >= {("farm_members", 2), ("parcels", 2)}


def test_given_two_owners_for_one_farm_when_inserting_then_the_database_refuses(migrated):
    farm = uuid.uuid4()
    sql("INSERT INTO farms (id, name) VALUES ($1, 'F')", farm)
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1, $2, 'owner')", farm, uuid.uuid4())
    with pytest.raises(Exception):
        sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1, $2, 'owner')", farm, uuid.uuid4())

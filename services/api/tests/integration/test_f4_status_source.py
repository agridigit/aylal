"""T023 - G1b: F4 feeds the F3 parcel status through `irrigation_need` (reader-side rules are tested in the worker suite)."""
import hashlib
import os
from pathlib import Path

from tests.helpers import sql
from tests.integration._f4 import call, world4  # noqa: F401

VECTOR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain")) / "vectors" / "f3_parcel_status.json"
F3_VECTOR_SHA256 = "bdb7e708175047885bab6e7e6f3459427f7be36378bb7fbc44317785c38d8937"


def test_given_the_f4_tables_then_the_irrigation_need_source_is_available():
    from app.monitoring.status_sources import available_sources

    tables = {r["table_name"] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    assert "irrigation_plans" in tables
    assert "irrigation_need" in available_sources(tables)


def test_given_the_f3_parcel_status_vector_then_it_is_unchanged():
    assert hashlib.sha256(VECTOR.read_bytes()).hexdigest() == F3_VECTOR_SHA256


def test_given_an_irrigation_item_on_a_parcel_when_the_worker_reads_its_status_then_only_an_assigned_parcel_exposes_it(client, token_for, world4):
    w = world4
    for parcel in (w["a1"], w["hidden"]):
        sql("INSERT INTO parcel_status_items (id, farm_id, parcel_id, source, severity, reason_key, reason_params, source_ref, observed_at)"
            " VALUES (gen_random_uuid(),$1,$2,'irrigation_need','act','status.irrigation_needed','{\"minutes\": 90}'::jsonb,gen_random_uuid(),now())", w["farm_a"], parcel)
    ok = call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/status")
    assert ok.status_code == 200 and [i["source"] for i in ok.json()["items"]] == ["irrigation_need"]
    assert call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['hidden']}/status").status_code == 404


def test_given_the_plan_table_then_it_is_the_name_f3_expects():
    from app.monitoring.status_sources import _TABLE_OF

    assert _TABLE_OF["irrigation_need"] == "irrigation_plans"

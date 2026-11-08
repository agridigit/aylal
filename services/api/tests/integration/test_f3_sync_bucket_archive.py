"""T021 (integration) - G3: archiving a parcel removes its rows (states, alerts, zones, points) from the worker AND staff
buckets, except the vigor history kept for staff. The bucket queries of infra/powersync/sync-rules.yaml are executed as written."""
import os
import re
from pathlib import Path

import yaml

from tests.helpers import sql
from tests.integration._f3 import seed_worker_rows, world3  # noqa: F401

INFRA = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "infra/powersync/sync-rules.yaml"
SYNCED = ("alerts", "parcel_status", "parcel_status_items", "attention_zones", "zone_observations")
HISTORY = ("parcel_vigor_points", "vigor_maps")


def _queries(bucket):
    return yaml.safe_load(INFRA.read_text(encoding="utf-8"))["bucket_definitions"][bucket]["data"]


def _rows(query, **bind):
    q = query
    for k, v in bind.items():
        q = q.replace(f"bucket.{k}", f"'{v}'::uuid")
    return [dict(r) for r in sql(q)]


def _table(query):
    return re.search(r"\bFROM (\w+)", query).group(1)


def _parcel_rows(bucket, table, **bind):
    out = []
    for q in _queries(bucket):
        if _table(q) == table:
            out += _rows(q, **bind)
    return out


def test_given_a_parcel_with_data_when_archived_then_the_worker_bucket_drops_it(world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    for t in SYNCED + HISTORY:
        assert any(r["parcel_id"] == w["a1"] for r in _parcel_rows("farm_worker_monitoring", t, parcel_id=w["a1"])), f"{t} not served before archiving"
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    for t in SYNCED + HISTORY:
        assert _parcel_rows("farm_worker_monitoring", t, parcel_id=w["a1"]) == [], t


def test_given_a_parcel_with_data_when_archived_then_the_staff_bucket_drops_it_except_the_vigor_history(world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    for t in SYNCED + HISTORY:
        assert any(r["parcel_id"] == w["a1"] for r in _parcel_rows("farm_data", t, farm_id=w["farm_a"])), f"{t} not served before archiving"
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    for t in SYNCED:
        assert not any(r["parcel_id"] == w["a1"] for r in _parcel_rows("farm_data", t, farm_id=w["farm_a"])), t
    for t in HISTORY:
        assert any(r["parcel_id"] == w["a1"] for r in _parcel_rows("farm_data", t, farm_id=w["farm_a"])), f"{t}: staff keep the history"

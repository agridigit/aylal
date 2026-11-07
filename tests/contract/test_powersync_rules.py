"""T037 - infra sync rules are the contract, and every bucket is filtered by farm membership (AC3.2, FR-018)."""
import os
from pathlib import Path

import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
CONTRACT = REPO / "specs/001-foundations/contracts/powersync-sync-rules.yaml"
INFRA = REPO / "infra/powersync/sync-rules.yaml"


def _rules() -> dict:
    return yaml.safe_load(INFRA.read_text(encoding="utf-8"))


def test_given_the_contract_when_comparing_then_infra_sync_rules_are_identical() -> None:
    assert INFRA.read_text(encoding="utf-8") == CONTRACT.read_text(encoding="utf-8")


def test_given_the_bucket_when_reading_parameters_then_it_is_filtered_by_the_requesting_member() -> None:
    bucket = _rules()["bucket_definitions"]["farm_data"]
    assert "farm_members" in bucket["parameters"]
    assert "request.user_id()" in bucket["parameters"]


def test_given_every_data_query_then_it_is_scoped_to_the_bucket_farm() -> None:
    queries = _rules()["bucket_definitions"]["farm_data"]["data"]
    assert len(queries) >= 5
    assert all("bucket.farm_id" in q for q in queries)


def test_given_synced_tables_then_trial_records_exclude_soft_deleted_and_conflicts_exclude_acknowledged() -> None:
    queries = " ".join(_rules()["bucket_definitions"]["farm_data"]["data"])
    assert "deleted_at IS NULL" in queries
    assert "acknowledged_at IS NULL" in queries

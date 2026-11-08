"""T028 - specs/006-dashboard-monitoring/contracts/powersync-sync-rules.yaml and infra/powersync/sync-rules.yaml agree,
and the contract itself is accepted by the PowerSync parser rules (every bucket declares what its queries reference)."""
import os
import re
from pathlib import Path

import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
CONTRACT = yaml.safe_load((REPO / "specs/006-dashboard-monitoring/contracts/powersync-sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
INFRA = yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
F3_TABLES = ("farm_weather", "alerts", "parcel_status", "parcel_status_items", "parcel_vigor_points", "vigor_maps", "attention_zones", "zone_observations", "daily_summaries")
SECRET = re.compile(r"\b(photo_key|map_key|raster_key|push_token|object_key)\b")


def _split(q):
    m = re.match(r"SELECT (.+?) FROM (\w+) WHERE (.+)$", q.strip(), re.S)
    if m is None:
        return None, set(), ""
    cols = {c.strip().split(" AS ")[-1].strip() for c in m.group(1).split(",")}
    return m.group(2), cols, m.group(3)


def _by_table(buckets):
    out = {}
    for name, b in buckets.items():
        for q in b.get("data", []):
            t, cols, where = _split(q)
            if t in F3_TABLES:
                out.setdefault(t, []).append((name, cols, where))
    return out


def _params(bucket):
    if not bucket.get("parameters"):
        return []
    return [c.strip().split(" AS ")[-1] for c in bucket["parameters"].split("SELECT ", 1)[1].split(" FROM ")[0].split(",")]


def test_given_the_contract_then_every_bucket_declares_the_parameters_its_queries_reference_and_every_query_covers_them():
    for name, b in CONTRACT.items():
        params = _params(b)
        for q in b["data"]:
            refs = set(re.findall(r"bucket\.(\w+)", q))
            assert refs == set(params), f"{name}: service rejects 'Query must cover all bucket parameters' ({refs} vs {params}) in {q[:60]}"


def test_given_the_contract_then_no_f3_query_selects_star_or_a_secret_column():
    for b in CONTRACT.values():
        for q in b["data"]:
            if any(f"FROM {t} " in q for t in F3_TABLES):
                assert "SELECT *" not in q and not SECRET.search(q), q


def test_given_the_infra_rules_then_every_contract_table_is_served_with_the_same_columns_and_filters():
    c, i = _by_table(CONTRACT), _by_table(INFRA)
    assert set(c) <= set(F3_TABLES)
    for t in c:
        assert t in i, f"infra rules do not serve {t}"
        for name, cols, where in c[t]:
            assert any(cols <= icols for _, icols, _ in i[t]), f"{t}: columns of the contract are not all served"
            if "parcel_archived_at IS NULL" in where:
                assert all("parcel_archived_at IS NULL" in w for _, _, w in i[t] if "valid = true" not in w and t not in ("parcel_vigor_points", "vigor_maps")), t


def test_given_the_infra_rules_then_no_f3_query_selects_star_or_a_secret_column():
    for b in INFRA.values():
        for q in b.get("data", []):
            if any(f"FROM {t} " in q for t in F3_TABLES):
                assert "SELECT *" not in q and not SECRET.search(q), q


def test_given_the_infra_rules_then_the_f3_buckets_exist_with_the_contract_parameters():
    for name in ("farm_worker_weather", "farm_worker_monitoring", "user_summaries"):
        assert name in INFRA, name
    assert INFRA["user_summaries"]["parameters"] == CONTRACT["user_summaries"]["parameters"]
    assert "removed_at IS NULL" in INFRA["user_summaries"]["parameters"]

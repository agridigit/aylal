"""T034b - G1: the worker never receives water-analysis, soil or leaching data through synchronisation (PowerSync rules + server write)."""
import json
import os
import re
from pathlib import Path

import pytest
import yaml

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    WORKER_ASSUMPTION_KEYS,
    compute,
    seed_analysis,
    seed_referentials,
    seed_weather_days,
    sync_op,
    sync_post,
    world4,
)

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
INFRA = yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
CONTRACT = yaml.safe_load((REPO / "specs/007-irrigation-water-balance/contracts/powersync-sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
BANNED_FOR_WORKER = {"assumptions", "leaching_fraction", "taw_mm", "raw_mm", "moisture_source"}
WORKER_BUCKETS = ("farm_worker_irrigation", "farm_worker_irrigation_own")
JOIN = re.compile(r"\bJOIN\b|\(\s*SELECT\b|\bIN\s*\(", re.I)


def _cols_of(q):
    m = re.match(r"SELECT (.+?) FROM (\w+)(?: WHERE (.+))?$", q.strip(), re.S)
    assert m, q
    return [c.strip().split(" AS ")[-1].strip() for c in m.group(1).split(",")], m.group(2), m.group(3) or ""


def _queries(buckets, name):
    assert name in buckets, f"{name} missing from the rules"
    return [_cols_of(q) for q in buckets[name]["data"]]


@pytest.mark.parametrize("rules", [INFRA, CONTRACT], ids=["infra", "contract"])
def test_given_the_rules_then_there_is_no_join_no_subquery_no_in_list_and_one_id_column_per_query(rules):
    names = [n for n in rules if "irrigation" in n]
    assert set(names) >= {"farm_irrigation", "farm_worker_irrigation", "farm_worker_irrigation_own", "irrigation_reference"}, names
    for name in names:
        b = rules[name]
        assert not JOIN.search(b.get("parameters", "") or "")
        for q in b["data"]:
            assert not JOIN.search(q), f"{name}: {q[:80]}"
            cols, _, _ = _cols_of(q)
            assert cols.count("id") == 1 and "*" not in "".join(cols), f"{name}: {q[:80]}"


@pytest.mark.parametrize("rules", [INFRA, CONTRACT], ids=["infra", "contract"])
def test_given_the_worker_buckets_then_plans_and_balances_carry_only_worker_safe_columns(rules):
    plans = [c for c, t, _ in _queries(rules, "farm_worker_irrigation") if t == "irrigation_plans"]
    days = [c for c, t, _ in _queries(rules, "farm_worker_irrigation") if t == "water_balance_days"]
    assert len(plans) == 1 and len(days) == 1
    assert "worker_assumptions" in plans[0] and not (BANNED_FOR_WORKER & set(plans[0]))
    assert not (BANNED_FOR_WORKER & set(days[0]))
    for bucket in WORKER_BUCKETS:
        for cols, table, _ in _queries(rules, bucket):
            assert not (BANNED_FOR_WORKER & set(cols)), (bucket, table)
            assert table != "water_analyses", f"{bucket} serves water_analyses"


@pytest.mark.parametrize("rules", [INFRA, CONTRACT], ids=["infra", "contract"])
def test_given_the_staff_bucket_then_it_has_the_complete_columns_and_the_analyses(rules):
    q = {t: c for c, t, _ in _queries(rules, "farm_irrigation")}
    assert {"assumptions", "leaching_fraction"} <= set(q["irrigation_plans"]) and "worker_assumptions" not in q["irrigation_plans"]
    assert {"taw_mm", "raw_mm", "moisture_source"} <= set(q["water_balance_days"])
    assert "water_analyses" in q and {"ec_ds_m", "water_source"} <= set(q["water_analyses"])


@pytest.mark.parametrize("rules", [INFRA, CONTRACT], ids=["infra", "contract"])
def test_given_the_author_data_then_events_are_served_only_in_the_own_bucket_and_applied_has_no_author_or_note(rules):
    for name in WORKER_BUCKETS:
        for cols, table, where in _queries(rules, name):
            if table == "irrigation_events":
                assert name == "farm_worker_irrigation_own" and "bucket.parcel_id" in where and "bucket.user_id" in where and "author_id" in where
            if table == "irrigation_applied":
                assert not ({"author_id", "note"} & set(cols))
    own = rules["farm_worker_irrigation_own"]
    for q in own["data"]:
        assert "bucket.parcel_id" in q and "bucket.user_id" in q and "parcel_archived_at IS NULL" in q
    assert "removed_at IS NULL" in rules["farm_irrigation"]["parameters"]


def test_given_the_infra_rules_then_they_equal_the_contract_for_every_f4_bucket():
    for name in ("farm_irrigation", "farm_worker_irrigation", "farm_worker_irrigation_own", "irrigation_reference"):
        c, i = _queries(CONTRACT, name), _queries(INFRA, name)
        assert sorted((t, tuple(cols)) for cols, t, _ in c) == sorted((t, tuple(cols)) for cols, t, _ in i), name
        assert CONTRACT[name].get("parameters") == INFRA[name].get("parameters")


def test_given_the_worker_bucket_queries_run_on_postgres_then_they_execute_as_written(world4):
    w = world4
    for q in INFRA["farm_worker_irrigation"]["data"]:
        sql(q.replace("bucket.parcel_id", f"'{w['a1']}'::uuid"))
    for q in INFRA["farm_irrigation"]["data"]:
        sql(q.replace("bucket.farm_id", f"'{w['farm_a']}'::uuid"))


def test_given_a_stored_plan_then_its_worker_assumptions_contain_no_key_outside_the_whitelist(world4):
    w = world4
    for row in sql("SELECT worker_assumptions, assumptions FROM irrigation_plans WHERE farm_id=$1", w["farm_a"]):
        wa = json.loads(row["worker_assumptions"]) if isinstance(row["worker_assumptions"], str) else row["worker_assumptions"]
        assert {a["key"] for a in wa} <= WORKER_ASSUMPTION_KEYS


def test_given_an_advice_computed_with_a_salty_analysis_then_the_server_writes_worker_assumptions_in_the_same_transaction_by_whitelist(world4):
    w = world4
    p = w["a1"]
    seed_referentials(w["farm_a"], p)
    seed_weather_days(w["farm_a"])
    sql("DELETE FROM irrigation_plans WHERE parcel_id=$1", p)
    seed_analysis(w["farm_a"], p, w["owner"], ec=5.0)  # above the fixture tolerance threshold
    out = compute(w["farm_a"], p)
    row = sql("SELECT assumptions, worker_assumptions, leaching_fraction FROM irrigation_plans WHERE parcel_id=$1", p)[0]
    full = json.loads(row["assumptions"]) if isinstance(row["assumptions"], str) else row["assumptions"]
    wa = json.loads(row["worker_assumptions"]) if isinstance(row["worker_assumptions"], str) else row["worker_assumptions"]
    assert float(row["leaching_fraction"] or 0) > 0 and out["kind"] in ("irrigate", "no_need", "postpone_rain")
    assert {"ece_ds_m", "water_source", "analysis_age_days"} <= {a["key"] for a in full}
    assert {a["key"] for a in wa} <= WORKER_ASSUMPTION_KEYS and wa


def test_given_a_client_sync_op_on_plans_or_worker_assumptions_then_it_is_refused_and_nothing_is_written(client, token_for, world4):
    import uuid

    w = world4
    before = sql("SELECT worker_assumptions FROM irrigation_plans WHERE parcel_id=$1", w["a1"])[0][0]
    op = sync_op("irrigation_plans", w["farm_a"], uuid.uuid4(), {"parcel_id": str(w["a1"]), "worker_assumptions": [{"key": "ece_ds_m", "value": 9, "source": "user"}]})
    r = sync_post(client, token_for(w["owner"]), [op])
    assert r.status_code in (400, 403, 422) or r.json()["results"][0]["status"] != "applied"
    assert sql("SELECT worker_assumptions FROM irrigation_plans WHERE parcel_id=$1", w["a1"])[0][0] == before

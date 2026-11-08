"""T065 - a worker sees only assigned parcels and no financial field, API and PowerSync rules (R6-A1, FR-020)."""
import os
import re
from pathlib import Path

import yaml

from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login  # noqa: F401

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
RULES = yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
FINANCIAL = re.compile(r"price|cost|amount|budget|revenue|expense|invoice|finance|salary|wage", re.I)
CASA = {"lat": 33.5731, "lon": -7.5898}


def _all_queries(bucket):
    return list(bucket["data"])


def _worker_buckets():
    found = {n: b for n, b in RULES.items() if "worker" in n}
    assert found, "no worker-scoped bucket in infra/powersync/sync-rules.yaml"
    return found


def test_given_the_sync_rules_then_a_dedicated_worker_bucket_exists_restricted_to_the_worker_role():
    buckets = _worker_buckets()
    assert buckets, "no worker-scoped bucket"
    for b in buckets.values():
        by_role = "role = 'worker'" in b["parameters"] and "removed_at IS NULL" in b["parameters"]
        by_assignment = "FROM worker_parcels WHERE user_id = request.user_id()" in b["parameters"]  # decisions.md
        assert by_role or by_assignment


def test_given_the_worker_bucket_then_parcels_are_limited_to_the_assigned_ones():
    for b in _worker_buckets().values():
        parcels = [q for q in _all_queries(b) if re.search(r"FROM\s+parcels", q)]
        if parcels:  # the service forbids joins and subqueries: the assignment is the bucket parameter
            assert "worker_parcels" in b["parameters"] and "user_id" in b["parameters"]


def test_given_the_worker_bucket_then_no_financial_table_or_column_nor_wildcard_on_farms_or_team_is_exposed():
    for b in _worker_buckets().values():
        for q in _all_queries(b):
            assert not FINANCIAL.search(q), q
            assert not re.search(r"SELECT\s+\*\s+FROM\s+(farms|farm_members|invitations|users|trial_records)\b", q), q


# Global reference buckets (readable by every member, workers included), named explicitly: T015 / F6 spec.
GLOBAL_CATALOG_BUCKETS = {"phyto_catalog"}
# Per-user buckets (F3 daily summaries): every ACTIVE member, workers included, reads only their own (farm_id, user_id) rows; see decisions F3.
PER_USER_BUCKETS = {"user_summaries"}


def test_given_the_general_buckets_then_no_one_gets_a_row_of_a_removed_member_and_workers_are_not_in_a_staff_bucket():
    for name, b in RULES.items():
        if "worker" in name:
            continue
        if name in GLOBAL_CATALOG_BUCKETS:
            assert not b.get("parameters"), name  # global catalogue: no per-user parameter, no farm data
            assert not re.search(r"farm_id|user_id", " ".join(_all_queries(b))), name
            continue
        assert "farm_members" in b["parameters"]
        assert "removed_at IS NULL" in b["parameters"], name
        if name in PER_USER_BUCKETS:
            assert "request.user_id() AS user_id" in b["parameters"], name
            continue
        assert "role != 'worker'" in b["parameters"], name  # workers excluded (the service rejects IN lists)


def test_given_a_worker_when_reading_the_farm_then_no_financial_field_is_returned(client, make_farm, token_for):
    import uuid

    owner, worker = uuid.uuid4(), uuid.uuid4()
    for u in (owner, worker):
        sql("INSERT INTO users (id, phone_e164, status) VALUES ($1, $2, 'active')", u, f"+2126{uuid.uuid4().int % 10**8:08d}")
    farm = make_farm({owner: "owner", worker: "worker"})
    r = client.get(f"/v1/farms/{farm}", headers=auth(token_for(worker)))
    assert r.status_code == 200 and r.json()["role"] == "worker"
    assert not [k for k in r.json() if FINANCIAL.search(k)]


def test_given_a_worker_when_writing_farm_admin_data_via_sync_then_nothing_is_written(client, make_farm, token_for):
    import uuid

    from tests.helpers import op

    owner, worker = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", worker: "worker"})
    other_worker = uuid.uuid4()
    r = client.post(
        "/v1/sync/upload",
        json={"ops": [{**op(farm, other_worker, kind="put", fields={"role": "manager"}), "table": "farm_members"}]},
        headers=auth(token_for(worker)),
    )
    assert r.status_code in (200, 403)
    assert sql("SELECT count(*) FROM farm_members WHERE farm_id=$1", farm)[0][0] == 2
    assert sql("SELECT role FROM farm_members WHERE user_id=$1", worker)[0][0] == "worker"

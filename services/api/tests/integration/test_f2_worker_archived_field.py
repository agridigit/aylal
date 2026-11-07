"""T007b - assigned worker + archived field (or deleted farm): REST 404, PowerSync rules return nothing, restore brings data back."""
import os
import re
from pathlib import Path

import pytest
import yaml

from tests.helpers import auth, op, sql
from tests.integration._f2 import add_block, add_field, add_season, assign, new_user

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
RULES = yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
CHILDREN = ("seasons", "field_blocks")


@pytest.fixture
def world(make_farm):
    owner, manager, worker = new_user(), new_user(), new_user()
    farm = make_farm({owner: "owner", manager: "manager", worker: "worker"})
    field = add_field(farm, "Mine")
    assign(farm, worker, field)
    return dict(owner=owner, manager=manager, worker=worker, farm=farm, field=field,
                season=add_season(farm, field), block=add_block(farm, field))


def worker_queries(table):
    qs = [q for n, b in RULES.items() if "worker" in n for q in b["data"] if re.search(rf"\bFROM\s+{table}\b", q)]
    assert qs, f"no worker sync rule on {table} in infra/powersync/sync-rules.yaml"
    return qs


def synced_rows(table, w):
    """Run the worker data queries of `table` as the service would, for the worker's bucket parameters."""
    n = 0
    for q in worker_queries(table):
        q = q.replace("bucket.parcel_id", f"'{w['field']}'").replace("bucket.farm_id", f"'{w['farm']}'").replace("bucket.user_id", f"'{w['worker']}'")
        n += len(sql(q))
    return n


def archive(client, token_for, w):
    r = client.delete(f"/v1/farms/{w['farm']}/fields/{w['field']}", headers=auth(token_for(w["owner"])))
    assert r.status_code == 204, r.text


def test_given_an_assigned_worker_when_the_field_is_archived_then_rest_returns_404_everywhere(client, token_for, world):
    w = world
    f, t = f"/v1/farms/{w['farm']}", token_for(w["worker"])
    assert client.get(f"{f}/fields/{w['field']}", headers=auth(t)).status_code == 200  # control
    archive(client, token_for, w)
    for p in (f"fields/{w['field']}", f"fields/{w['field']}/blocks", f"fields/{w['field']}/seasons",
              f"fields/{w['field']}/seasons/{w['season']}"):
        assert client.get(f"{f}/{p}", headers=auth(t)).status_code == 404, p
    r = client.get(f"{f}/fields", headers=auth(t))
    assert r.status_code == 200
    items = r.json()["items"] if isinstance(r.json(), dict) else r.json()
    assert items == []


@pytest.mark.parametrize("table", ["parcels", *CHILDREN])
def test_given_an_assigned_worker_when_the_field_is_archived_then_the_worker_sync_rules_return_no_row_and_restore_brings_them_back(
    client, token_for, world, table,
):
    w = world
    assert synced_rows(table, w) >= 1, "control: the assigned worker syncs the field and its children"
    archive(client, token_for, w)
    assert synced_rows(table, w) == 0, f"{table}: archived field still synced to the worker (history leak)"
    r = client.post(f"/v1/farms/{w['farm']}/fields/{w['field']}/restore", headers=auth(token_for(w["manager"])))
    assert r.status_code == 200, r.text
    assert synced_rows(table, w) >= 1


def test_given_the_f2_worker_rules_then_no_join_subquery_or_in_list_and_children_filter_on_the_denormalized_parent_state():
    for name, bucket in RULES.items():
        for q in bucket["data"]:
            assert not re.search(r"\bJOIN\b|\(\s*SELECT\b|\bIN\s*\(", q, re.I), f"{name}: {q}"
    for table in CHILDREN:
        for q in worker_queries(table):
            assert "parcel_archived_at IS NULL" in q, q
    assert all("archived_at IS NULL" in q for q in worker_queries("parcels"))
    assert not any("field_commands" in q for b in RULES.values() for q in b["data"] if b in
                   [RULES[n] for n in RULES if "worker" in n])


def test_given_a_field_archived_and_restored_then_children_carry_the_parent_state(client, token_for, world):
    w = world
    archive(client, token_for, w)
    for t in CHILDREN:
        assert sql(f"SELECT count(*) FROM {t} WHERE field_id=$1 AND parcel_archived_at IS NOT NULL", w["field"])[0][0] == 1
    client.post(f"/v1/farms/{w['farm']}/fields/{w['field']}/restore", headers=auth(token_for(w["owner"])))
    for t in CHILDREN:
        assert sql(f"SELECT count(*) FROM {t} WHERE field_id=$1 AND parcel_archived_at IS NULL", w["field"])[0][0] == 1


def test_given_an_assigned_worker_when_the_farm_is_deleted_then_rest_returns_404(client, token_for, world):
    w = world
    sql("UPDATE farms SET deleted_at=now() WHERE id=$1", w["farm"])
    for p in ("fields", f"fields/{w['field']}", f"fields/{w['field']}/blocks", f"fields/{w['field']}/seasons"):
        assert client.get(f"/v1/farms/{w['farm']}/{p}", headers=auth(token_for(w["worker"]))).status_code == 404, p


def test_given_an_assigned_worker_and_an_archived_field_when_uploading_then_every_write_is_refused(client, token_for, world):
    w = world
    archive(client, token_for, w)
    o = op(w["farm"], w["season"], kind="patch", fields={"variety": "Late"})
    o["table"] = "seasons"
    r = client.post("/v1/sync/upload", json={"ops": [o]}, headers=auth(token_for(w["worker"])))
    assert r.status_code in (403, 404), r.text
    assert sql("SELECT count(*) FROM seasons WHERE variety='Late'")[0][0] == 0

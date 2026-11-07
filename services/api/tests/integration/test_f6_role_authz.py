"""T011 - G1: 403 per role, worker visibility, forced worker status, no physical deletion."""

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import add_operation, add_registry, op_body, world  # noqa: F401


def _h(token_for, user):
    return auth(token_for(user))


def test_given_owner_and_manager_when_creating_an_operation_then_it_is_validated(client, token_for, world):
    w = world
    for who in ("owner", "manager"):
        r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=_h(token_for, w[who]), json=op_body([w["a1"]]))
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "validated"


def test_given_a_worker_when_creating_with_a_forced_status_then_it_is_pending_validation_or_planned(client, token_for, world):
    w = world
    h = _h(token_for, w["worker"])
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=h, json=op_body([w["a1"]], status="validated"))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending_validation"
    future = (__import__("datetime").date.today() + __import__("datetime").timedelta(days=3)).isoformat()
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=h, json=op_body([w["a1"]], performed_on=future, status="validated"))
    assert r.status_code == 201 and r.json()["status"] == "planned", r.text


@pytest.mark.parametrize("action", ["validate", "correct", "registry_read", "registry_export"])
def test_given_a_worker_when_doing_a_staff_action_then_403_while_staff_succeeds(client, token_for, world, action):
    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"], status="pending_validation")
    f = f"/v1/farms/{w['farm_a']}"
    calls = {
        "validate": ("POST", f"{f}/operations/{oid}/validate", None),
        "correct": ("PATCH", f"{f}/operations/{oid}", {"note": "fixed"}),
        "registry_read": ("GET", f"{f}/registry", None),
        "registry_export": ("POST", f"{f}/registry/exports", {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "pdf", "scope": "farm", "lang": "fr"}),
    }
    method, path, body = calls[action]
    staff = client.request(method, path, headers=_h(token_for, w["manager"]), json=body)
    assert staff.status_code in (200, 202), staff.text
    r = client.request(method, path, headers=_h(token_for, w["worker"]), json=body)
    assert r.status_code == 403, r.text


def test_given_a_worker_when_cancelling_someone_elses_operation_then_403_and_status_is_unchanged(client, token_for, world):
    w = world
    others = add_operation(w["farm_a"], w["manager"], w["a1"], status="planned")
    mine = add_operation(w["farm_a"], w["worker"], w["a1"], status="planned")
    h = _h(token_for, w["worker"])
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{mine}/cancel", headers=h).status_code == 200
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{others}/cancel", headers=h)
    assert r.status_code == 403, r.text
    assert sql("SELECT status FROM operations WHERE id=$1", others)[0][0] == "planned"


def test_given_a_worker_when_using_an_unassigned_or_archived_parcel_then_404(client, token_for, world):
    w = world
    h = _h(token_for, w["worker"])
    ok = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=h, json=op_body([w["a1"]]))
    assert ok.status_code == 201, ok.text
    assert client.post(f"/v1/farms/{w['farm_a']}/operations", headers=h, json=op_body([w["a2"]])).status_code == 404
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    assert client.post(f"/v1/farms/{w['farm_a']}/operations", headers=h, json=op_body([w["a1"]])).status_code == 404


def test_given_a_worker_when_listing_then_only_own_lines_on_assigned_parcels(client, token_for, world):
    w = world
    mine = add_operation(w["farm_a"], w["worker"], w["a1"])
    add_operation(w["farm_a"], w["manager"], w["a1"])
    add_operation(w["farm_a"], w["worker"], w["a2"])
    r = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=_h(token_for, w["worker"]))
    assert r.status_code == 200, r.text
    assert [i["id"] for i in r.json()["items"]] == [str(mine)]
    assert len(client.get(f"/v1/farms/{w['farm_a']}/operations", headers=_h(token_for, w["owner"])).json()["items"]) == 3


def test_given_registry_rows_then_none_is_synchronised_to_the_worker_bucket():
    import os
    import pathlib

    text = (pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "infra/powersync/sync-rules.yaml").read_text()
    assert "farm_worker_ops:" in text, "F6 worker bucket missing from sync rules"
    assert "registry_entries" not in text.split("farm_worker_ops:")[1]


def test_given_the_api_then_no_f6_route_deletes_physically(client):
    paths = client.get("/openapi.json").json()["paths"]
    f6 = {p: i for p, i in paths.items() if "/operations" in p or "/registry" in p}
    assert f6, "no F6 route is served"
    assert all("delete" not in item for item in f6.values())

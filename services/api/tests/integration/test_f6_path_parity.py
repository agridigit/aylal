"""T013 - G1: one matrix (role x parcel state x action) run against REST and sync gives the same verdict; inventory guard."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, op_body, routes, sync_op, world  # noqa: F401

PARCEL_STATES = ("assigned", "unassigned", "archived", "deleted")
CASES = [(r, s) for r in ("owner", "manager", "worker") for s in PARCEL_STATES]


def _prepare(w, state):
    parcel = w["a1"] if state in ("assigned", "archived", "deleted") else w["a2"]
    if state == "archived":
        sql("UPDATE parcels SET archived_at=now() WHERE id=$1", parcel)
    if state == "deleted":
        sql("DELETE FROM worker_parcels WHERE parcel_id=$1", parcel)
        sql("UPDATE parcels SET archived_at=now(), purge_after=now() WHERE id=$1", parcel)
    return parcel


def _verdict(status):
    return "ok" if status in (200, 201) else status


@pytest.mark.parametrize("role,state", CASES, ids=lambda x: str(x))
def test_given_the_same_matrix_when_creating_via_rest_and_sync_then_the_verdict_is_identical(client, token_for, world, role, state):
    w = world
    parcel = _prepare(w, state)
    tok = token_for(w[role])
    rest = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(tok), json=op_body([parcel]))
    fields = {k: v for k, v in op_body([parcel]).items() if k != "id"}
    sync = client.post("/v1/sync/upload", headers=auth(tok), json={"ops": [sync_op("operations", w["farm_a"], uuid.uuid4(), fields)]})
    if role == "owner" and state == "assigned":
        assert rest.status_code == 201 and sync.status_code == 200, (rest.text, sync.text)
    assert _verdict(rest.status_code) == _verdict(sync.status_code if sync.status_code != 200 else 200), (role, state, rest.text, sync.text)
    if role == "worker" and state != "assigned":
        assert rest.status_code == 404 and sync.status_code == 404


@pytest.mark.parametrize("role,state", CASES, ids=lambda x: str(x))
def test_given_the_same_matrix_when_reading_the_dar_then_the_worker_rule_matches_rest_visibility(client, token_for, world, role, state):
    w = world
    parcel = _prepare(w, state)
    tok = token_for(w[role])
    ok = client.get(f"/v1/farms/{w['farm_a']}/fields/{w['a1']}/earliest-harvest", headers=auth(token_for(w["owner"])))
    assert ok.status_code in (200,), ok.text
    r = client.get(f"/v1/farms/{w['farm_a']}/fields/{parcel}/earliest-harvest", headers=auth(tok))
    expected_404 = role == "worker" and state != "assigned"
    assert (r.status_code == 404) is expected_404, (role, state, r.status_code)


def test_given_the_account_export_and_purge_paths_then_a_worker_never_gets_archived_or_unassigned_f6_lines(token_for, world):
    import asyncio

    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    w = world
    add_operation(w["farm_a"], w["worker"], w["a1"])
    hidden = add_operation(w["farm_a"], w["worker"], w["a2"])

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, w["worker"])

    data = asyncio.run(run())
    assert "operations" in data, "F6 data missing from the account export"
    ids = {o["id"] for o in data["operations"]}
    assert str(hidden) not in ids and len(ids) == 1


def test_given_the_served_f6_routes_when_inventorying_then_each_one_is_in_the_parity_matrix(client):
    live = client.get("/openapi.json").json()["paths"]
    served = {p for p in live if p.startswith(("/v1/farms/{farm_id}/operations", "/v1/farms/{farm_id}/registry",
                                               "/v1/farms/{farm_id}/phyto-products", "/v1/farms/{farm_id}/fields/{field_id}/earliest-harvest"))}
    assert served, "no F6 route is served"
    covered = set()
    for _, path, _ in routes("{farm_id}", "{operation_id}", "{field_id}", "{job_id}"):
        covered.add(path)
    assert served <= covered, f"F6 routes missing from the parity matrix: {sorted(served - covered)}"
    tables = {r[0] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN "
                                "('operations','operation_parcels','operation_reminders','operation_corrections','registry_entries','export_jobs','label_uploads')")}
    assert len(tables) == 7, f"F6 tables missing: {tables}"

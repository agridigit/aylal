"""T054 - POST /v1/me/deletion, /v1/me/export, deletion impact (R8-A1, R8-A2, R8-A3, FR-026)."""
import datetime as dt

from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login, relogin  # noqa: F401

CASA = {"lat": 33.5731, "lon": -7.5898}


def _h(s):
    return auth(s["access_token"])


def _farm(client, s, name="Ferme"):
    return client.post("/v1/farms", json={"name": name, "location": CASA}, headers=_h(s)).json()["id"]


def test_given_a_confirmed_request_then_202_and_the_deadline_is_30_days_ahead(client):
    s = login(client)
    before = dt.datetime.now(dt.UTC)
    r = client.post("/v1/me/deletion", json={"confirm": True}, headers=_h(s))
    assert r.status_code == 202
    deadline = dt.datetime.fromisoformat(r.json()["deletion_deadline"])
    assert abs((deadline - before) - dt.timedelta(days=30)) < dt.timedelta(minutes=5)
    row = sql("SELECT status, deletion_requested_at FROM users WHERE id = $1::uuid", s["user"]["id"])[0]
    assert row["status"] == "deletion_requested" and row["deletion_requested_at"] is not None


def test_given_no_confirmation_when_deleting_then_422_and_nothing_changes(client):
    s = login(client)
    for body in ({}, {"confirm": False}):
        assert client.post("/v1/me/deletion", json=body, headers=_h(s)).status_code == 422
    assert sql("SELECT status FROM users WHERE id = $1::uuid", s["user"]["id"])[0][0] != "deletion_requested"


def test_given_no_session_when_deleting_then_401(client):
    assert client.post("/v1/me/deletion", json={"confirm": True}).status_code == 401


def test_given_a_confirmed_request_then_every_device_is_signed_out(client):
    s1 = login(client)
    s2 = relogin(client)  # second device, other token family
    assert client.post("/v1/me/deletion", json={"confirm": True}, headers=_h(s1)).status_code == 202
    for s in (s1, s2):
        assert client.post("/v1/auth/refresh", json={"refresh_token": s["refresh_token"]}).status_code == 401
    assert client.get("/v1/me", headers=_h(s1)).status_code == 401
    assert sql("SELECT count(*) FROM refresh_tokens WHERE user_id=$1::uuid AND revoked_at IS NULL", s1["user"]["id"])[0][0] == 0


def test_given_an_owner_with_members_when_asking_the_impact_then_the_farm_and_member_count_are_returned(client, token_for):
    owner = login(client)
    farm = _farm(client, owner, "Atlas")
    solo = _farm(client, owner, "Solo")
    worker = login(client, "+212611112222")
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'worker')", farm, worker["user"]["id"])
    r = client.get("/v1/me/deletion/impact", headers=_h(owner))
    assert r.status_code == 200
    assert r.json()["owned_farms"] == [{"farm_id": farm, "name": "Atlas", "other_members": 1}]
    assert solo not in [f["farm_id"] for f in r.json()["owned_farms"]]


def test_given_a_non_owner_when_asking_the_impact_then_the_list_is_empty(client):
    owner = login(client)
    farm = _farm(client, owner)
    manager = login(client, "+212611112222")
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'manager')", farm, manager["user"]["id"])
    assert client.get("/v1/me/deletion/impact", headers=_h(manager)).json()["owned_farms"] == []


def test_given_an_export_request_then_202_with_an_export_id(client):
    s = login(client)
    r = client.post("/v1/me/export", headers=_h(s))
    assert r.status_code == 202 and r.json()["export_id"]
    assert client.post("/v1/me/export").status_code == 401


def test_given_a_user_with_data_when_building_the_export_then_it_is_complete_and_only_theirs(client):
    import asyncio

    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    mine, other = login(client), login(client, "+212611112222")
    client.post("/v1/me/consents", json={"purpose": "data_policy", "text_version": "2026-01"}, headers=_h(mine))
    client.patch("/v1/me", json={"display_name": "Hassan"}, headers=_h(mine))
    farm = _farm(client, mine, "Atlas")
    foreign = _farm(client, other, "Autre")
    sql("INSERT INTO trial_records (id, farm_id, author_id, title) VALUES (gen_random_uuid(), $1::uuid, $2::uuid, 'Mon essai')", farm, mine["user"]["id"])
    sql("INSERT INTO trial_records (id, farm_id, author_id, title) VALUES (gen_random_uuid(), $1::uuid, $2::uuid, 'Essai voisin')", foreign, other["user"]["id"])

    async def _run():
        async with sessionmaker() as session:
            return await build_export(session, mine["user"]["id"])

    data = asyncio.run(_run())
    assert data["profile"]["phone"] == mine["user"]["phone"] and data["profile"]["display_name"] == "Hassan"
    assert [c["purpose"] for c in data["consents"]] == ["data_policy"]
    assert [(f["id"], f["role"]) for f in data["farms"]] == [(farm, "owner")]
    assert [r["title"] for r in data["records"]] == ["Mon essai"]
    blob = str(data)
    assert foreign not in blob and "Essai voisin" not in blob and other["user"]["phone"] not in blob
    assert "token_hash" not in blob and "code_hash" not in blob

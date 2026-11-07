"""T064 - invitations (201/409/422/30 d), honored at sign-in, cancel, role change, removal (R6-A2..A5)."""
import datetime as dt

import pytest

from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login, relogin  # noqa: F401

CASA = {"lat": 33.5731, "lon": -7.5898}
INVITEE = "+212699887766"


def _h(s):
    return auth(s["access_token"])


@pytest.fixture
def team(client):
    owner = login(client, "+212611110001")
    manager, worker = login(client, "+212611110002"), login(client, "+212611110003")
    farm = client.post("/v1/farms", json={"name": "Atlas", "location": CASA}, headers=_h(owner)).json()["id"]
    for s, role in ((manager, "manager"), (worker, "worker")):
        sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, $3)", farm, s["user"]["id"], role)
    return dict(owner=owner, manager=manager, worker=worker, farm=farm)


def _invite(client, s, farm, phone=INVITEE, role="worker"):
    return client.post(f"/v1/farms/{farm}/invitations", json={"phone": phone, "role": role}, headers=_h(s))


def test_given_an_owner_when_inviting_a_number_then_201_pending_and_expires_in_30_days(client, team):
    r = _invite(client, team["owner"], team["farm"], "0699887766", "manager")
    assert r.status_code == 201
    body = r.json()
    assert body["phone"] == INVITEE and body["role"] == "manager" and body["status"] == "pending"
    assert abs(dt.datetime.fromisoformat(body["expires_at"]) - dt.datetime.now(dt.UTC) - dt.timedelta(days=30)) < dt.timedelta(minutes=5)
    assert set(body) <= {"id", "phone", "role", "status", "expires_at"}  # no secret/token/code in the answer


@pytest.mark.parametrize("who", ["manager", "worker"])
def test_given_a_manager_or_worker_when_inviting_then_403_and_nothing_is_stored(client, team, who):
    assert _invite(client, team[who], team["farm"]).status_code == 403
    assert sql("SELECT count(*) FROM invitations")[0][0] == 0


def test_given_a_non_member_when_inviting_then_404(client, team):
    assert _invite(client, login(client, "+212611119999"), team["farm"]).status_code == 404


@pytest.mark.parametrize("phone", ["12345", "+33612345678", "+14155550123", ""])
def test_given_an_invalid_or_foreign_number_when_inviting_then_422(client, team, phone):
    assert _invite(client, team["owner"], team["farm"], phone).status_code == 422


@pytest.mark.parametrize("role", ["owner", "admin", ""])
def test_given_an_invalid_role_when_inviting_then_422(client, team, role):
    assert _invite(client, team["owner"], team["farm"], role=role).status_code == 422


def test_given_an_existing_member_when_inviting_their_number_then_409(client, team):
    assert _invite(client, team["owner"], team["farm"], team["worker"]["user"]["phone"]).status_code == 409


def test_given_a_pending_invitation_when_inviting_again_then_it_is_refreshed_not_duplicated(client, team):
    _invite(client, team["owner"], team["farm"])
    _invite(client, team["owner"], team["farm"], role="manager")
    rows = sql("SELECT role FROM invitations WHERE phone_e164 = $1 AND status = 'pending'", INVITEE)
    assert [r[0] for r in rows] == ["manager"]


@pytest.mark.parametrize("role", ["manager", "worker"])
def test_given_an_invitation_when_the_number_signs_up_then_the_person_joins_with_the_planned_role(client, team, role):
    _invite(client, team["owner"], team["farm"], role=role)
    s = login(client, INVITEE)
    assert {f["id"]: f["role"] for f in s["farms"]} == {team["farm"]: role}
    assert sql("SELECT status FROM invitations WHERE phone_e164 = $1", INVITEE)[0][0] == "accepted"
    assert client.get("/v1/farms", headers=_h(s)).json()[0]["role"] == role


def test_given_an_invitation_for_an_existing_account_when_it_signs_in_then_it_joins(client, team):
    existing = login(client, INVITEE)
    assert existing["farms"] == []
    _invite(client, team["owner"], team["farm"])
    again = relogin(client, INVITEE)
    assert [f["role"] for f in again["farms"]] == ["worker"]


def test_given_an_accepted_invitation_when_the_member_is_removed_then_signing_in_again_does_not_rejoin(client, team):
    _invite(client, team["owner"], team["farm"])
    s = login(client, INVITEE)
    assert client.delete(f"/v1/farms/{team['farm']}/members/{s['user']['id']}", headers=_h(team["owner"])).status_code == 204
    assert relogin(client, INVITEE)["farms"] == []  # single use: the invitation is spent
    assert sql("SELECT count(*) FROM farm_members WHERE farm_id=$1::uuid AND user_id=$2::uuid AND removed_at IS NULL", team["farm"], s["user"]["id"])[0][0] == 0


def test_given_an_expired_invitation_when_the_number_signs_up_then_it_does_not_join(client, team):
    _invite(client, team["owner"], team["farm"])
    sql("UPDATE invitations SET expires_at = now() - interval '1 second' WHERE phone_e164 = $1", INVITEE)
    assert login(client, INVITEE)["farms"] == []
    assert sql("SELECT status FROM invitations WHERE phone_e164 = $1", INVITEE)[0][0] in ("pending", "expired")


def test_given_a_cancelled_invitation_when_the_number_signs_up_then_it_does_not_join(client, team):
    inv = _invite(client, team["owner"], team["farm"]).json()["id"]
    assert client.delete(f"/v1/farms/{team['farm']}/invitations/{inv}", headers=_h(team["owner"])).status_code == 204
    assert login(client, INVITEE)["farms"] == []
    assert sql("SELECT status FROM invitations WHERE id = $1::uuid", inv)[0][0] == "cancelled"


def test_given_an_invitation_of_another_farm_when_cancelling_then_404_and_it_stays_pending(client, team):
    other_owner = login(client, "+212611118888")
    other = client.post("/v1/farms", json={"name": "Autre", "location": CASA}, headers=_h(other_owner)).json()["id"]
    inv = _invite(client, other_owner, other).json()["id"]
    assert client.delete(f"/v1/farms/{team['farm']}/invitations/{inv}", headers=_h(team["owner"])).status_code == 404
    assert sql("SELECT status FROM invitations WHERE id = $1::uuid", inv)[0][0] == "pending"


def test_given_the_owner_when_changing_a_role_then_the_new_rights_apply_on_the_next_request(client, team):
    w = team["worker"]
    assert client.patch(f"/v1/farms/{team['farm']}", json={"name": "X"}, headers=_h(w)).status_code == 403
    r = client.patch(f"/v1/farms/{team['farm']}/members/{w['user']['id']}", json={"role": "manager"}, headers=_h(team["owner"]))
    assert r.status_code == 200 and r.json()["role"] == "manager"
    assert client.patch(f"/v1/farms/{team['farm']}", json={"name": "X"}, headers=_h(w)).status_code == 200  # DB is the truth, not the token
    client.patch(f"/v1/farms/{team['farm']}/members/{w['user']['id']}", json={"role": "worker"}, headers=_h(team["owner"]))
    assert client.patch(f"/v1/farms/{team['farm']}", json={"name": "Y"}, headers=_h(w)).status_code == 403


@pytest.mark.parametrize("who", ["manager", "worker"])
def test_given_a_manager_or_worker_when_changing_a_role_or_removing_then_403(client, team, who):
    target = team["worker"]["user"]["id"]
    assert client.patch(f"/v1/farms/{team['farm']}/members/{target}", json={"role": "manager"}, headers=_h(team[who])).status_code == 403
    assert client.delete(f"/v1/farms/{team['farm']}/members/{target}", headers=_h(team[who])).status_code == 403


def test_given_the_owner_when_changing_to_owner_or_touching_the_owner_then_it_is_refused(client, team):
    owner_id = team["owner"]["user"]["id"]
    w = team["worker"]["user"]["id"]
    assert client.patch(f"/v1/farms/{team['farm']}/members/{w}", json={"role": "owner"}, headers=_h(team["owner"])).status_code == 422
    assert client.patch(f"/v1/farms/{team['farm']}/members/{owner_id}", json={"role": "worker"}, headers=_h(team["owner"])).status_code == 403
    assert client.delete(f"/v1/farms/{team['farm']}/members/{owner_id}", headers=_h(team["owner"])).status_code == 403
    assert client.delete(f"/v1/farms/{team['farm']}/members/{owner_id}", headers=_h(team["manager"])).status_code == 403


def test_given_the_owner_when_removing_a_member_then_they_lose_access_immediately(client, team):
    w = team["worker"]
    assert client.get(f"/v1/farms/{team['farm']}", headers=_h(w)).status_code == 200
    assert client.delete(f"/v1/farms/{team['farm']}/members/{w['user']['id']}", headers=_h(team["owner"])).status_code == 204
    assert client.get(f"/v1/farms/{team['farm']}", headers=_h(w)).status_code == 404
    assert client.get("/v1/farms", headers=_h(w)).json() == []
    assert w["user"]["id"] not in [m["user_id"] for m in client.get(f"/v1/farms/{team['farm']}/members", headers=_h(team["owner"])).json()]


def test_given_a_user_of_another_farm_when_changing_roles_or_removing_then_404(client, team):
    stranger = login(client, "+212611118888")
    client.post("/v1/farms", json={"name": "S", "location": CASA}, headers=_h(stranger))
    w = team["worker"]["user"]["id"]
    assert client.patch(f"/v1/farms/{team['farm']}/members/{w}", json={"role": "manager"}, headers=_h(stranger)).status_code == 404
    assert client.delete(f"/v1/farms/{team['farm']}/members/{w}", headers=_h(stranger)).status_code == 404
    assert client.get(f"/v1/farms/{team['farm']}/members", headers=_h(stranger)).status_code == 404


def test_given_parcels_of_two_farms_when_assigning_then_a_foreign_parcel_gives_404_and_nothing_is_written(client, team):
    mine, foreign = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    other_farm = client.post("/v1/farms", json={"name": "O", "location": CASA}, headers=_h(login(client, "+212611118888"))).json()["id"]
    poly = "ST_GeomFromText('POLYGON((0 0,0 1,1 1,1 0,0 0))', 4326)"
    sql(f"INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES ($1::uuid, $2::uuid, 'P', {poly}, 0.5)", mine, team["farm"])
    sql(f"INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES ($1::uuid, $2::uuid, 'Q', {poly}, 0.5)", foreign, other_farm)
    w = team["worker"]["user"]["id"]
    url = f"/v1/farms/{team['farm']}/members/{w}/parcels"
    assert client.put(url, json={"parcel_ids": [mine, foreign]}, headers=_h(team["owner"])).status_code == 404
    assert sql("SELECT count(*) FROM worker_parcels")[0][0] == 0
    assert client.put(url, json={"parcel_ids": [mine]}, headers=_h(team["manager"])).status_code == 200

"""T059 - second farm, memberships with role, isolation (R5-A1, R5-A3)."""
from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login, relogin  # noqa: F401

CASA = {"lat": 33.5731, "lon": -7.5898}
RABAT = {"lat": 34.0209, "lon": -6.8416}


def _h(s):
    return auth(s["access_token"])


def test_given_an_owner_when_adding_a_second_farm_then_both_are_listed_as_owner(client):
    s = login(client)
    a = client.post("/v1/farms", json={"name": "A", "location": CASA}, headers=_h(s)).json()
    b = client.post("/v1/farms", json={"name": "B", "location": RABAT}, headers=_h(s)).json()
    listed = {f["id"]: f["role"] for f in client.get("/v1/farms", headers=_h(s)).json()}
    assert listed == {a["id"]: "owner", b["id"]: "owner"}
    assert a["id"] != b["id"] and a["commune_id"] != b["commune_id"]


def test_given_two_farms_when_reading_each_detail_then_each_has_its_own_data(client):
    s = login(client)
    a = client.post("/v1/farms", json={"name": "A", "location": CASA}, headers=_h(s)).json()
    b = client.post("/v1/farms", json={"name": "B", "location": RABAT}, headers=_h(s)).json()
    assert client.get(f"/v1/farms/{a['id']}", headers=_h(s)).json()["name"] == "A"
    assert client.get(f"/v1/farms/{b['id']}", headers=_h(s)).json()["name"] == "B"


def test_given_a_membership_in_someone_elses_farm_when_listing_then_it_appears_with_my_role_and_no_ownership(client):
    owner, member = login(client), login(client, "+212611112222")
    farm = client.post("/v1/farms", json={"name": "Atlas", "location": CASA}, headers=_h(owner)).json()
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'manager')", farm["id"], member["user"]["id"])
    mine = client.post("/v1/farms", json={"name": "Mienne", "location": RABAT}, headers=_h(member)).json()
    listed = {f["id"]: f for f in client.get("/v1/farms", headers=_h(member)).json()}
    assert listed[farm["id"]]["role"] == "manager" and listed[farm["id"]]["owner_id"] == owner["user"]["id"]
    assert listed[mine["id"]]["role"] == "owner"


def test_given_a_removed_membership_or_deleted_farm_when_listing_then_the_farm_is_gone(client):
    owner, member = login(client), login(client, "+212611112222")
    a = client.post("/v1/farms", json={"name": "A", "location": CASA}, headers=_h(owner)).json()["id"]
    b = client.post("/v1/farms", json={"name": "B", "location": CASA}, headers=_h(owner)).json()["id"]
    for f in (a, b):
        sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'worker')", f, member["user"]["id"])
    sql("UPDATE farm_members SET removed_at = now() WHERE farm_id = $1::uuid AND user_id = $2::uuid", a, member["user"]["id"])
    sql("UPDATE farms SET deleted_at = now() WHERE id = $1::uuid", b)
    assert client.get("/v1/farms", headers=_h(member)).json() == []
    assert client.get(f"/v1/farms/{a}", headers=_h(member)).status_code == 404
    assert client.get(f"/v1/farms/{b}", headers=_h(member)).status_code == 404


def test_given_the_session_after_login_then_every_membership_with_role_is_restored(client):
    owner, member = login(client), login(client, "+212611112222")
    a = client.post("/v1/farms", json={"name": "A", "location": CASA}, headers=_h(owner)).json()["id"]
    b = client.post("/v1/farms", json={"name": "B", "location": RABAT}, headers=_h(member)).json()["id"]
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'worker')", a, member["user"]["id"])
    again = relogin(client, "+212611112222")
    assert {f["id"]: f["role"] for f in again["farms"]} == {a: "worker", b: "owner"}

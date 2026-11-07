"""T046 - POST/GET /v1/farms (R4-A1, R4-A2, R4-A5)."""
import pytest

from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login  # noqa: F401

CASA = {"lat": 33.5731, "lon": -7.5898}


def _h(s):
    return auth(s["access_token"])


def test_given_a_name_and_a_point_when_creating_then_201_and_the_caller_is_the_only_owner(client):
    s = login(client)
    r = client.post("/v1/farms", json={"name": "Ferme Atlas", "location": CASA, "area_ha": 2.5}, headers=_h(s))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Ferme Atlas" and body["role"] == "owner" and body["owner_id"] == s["user"]["id"]
    owners = sql("SELECT user_id FROM farm_members WHERE farm_id = $1::uuid AND role = 'owner'", body["id"])
    assert [str(o[0]) for o in owners] == [s["user"]["id"]]


def test_given_a_client_supplied_owner_when_creating_then_it_is_ignored(client):
    s = login(client)
    r = client.post("/v1/farms", json={"name": "F", "location": CASA, "owner_id": "00000000-0000-0000-0000-000000000001"}, headers=_h(s))
    assert r.status_code == 201 and r.json()["owner_id"] == s["user"]["id"]


def test_given_a_point_when_creating_then_the_commune_is_deduced_and_stored(client):
    s = login(client)
    r = client.post("/v1/farms", json={"name": "F", "location": CASA}, headers=_h(s))
    expected = client.get("/v1/geo/locate", params=CASA, headers=_h(s)).json()["id"]
    assert r.json()["commune_id"] == expected
    assert sql("SELECT commune_id FROM farms WHERE id = $1::uuid", r.json()["id"])[0][0] == expected


def test_given_no_area_when_creating_then_the_farm_is_created_anyway(client):
    s = login(client)
    r = client.post("/v1/farms", json={"name": "F", "location": CASA}, headers=_h(s))
    assert r.status_code == 201 and r.json()["area_ha"] is None


@pytest.mark.parametrize(
    "body",
    [{"location": CASA}, {"name": "", "location": CASA}, {"name": "F"}, {"name": "F", "location": CASA, "area_ha": -1}],
)
def test_given_a_missing_name_or_location_when_creating_then_422(client, body):
    s = login(client)
    assert client.post("/v1/farms", json=body, headers=_h(s)).status_code == 422
    assert sql("SELECT count(*) FROM farms")[0][0] == 0


def test_given_no_session_when_creating_then_401(client):
    assert client.post("/v1/farms", json={"name": "F", "location": CASA}).status_code == 401


def test_given_memberships_when_listing_then_each_farm_carries_my_role(client):
    owner, other = login(client), login(client, "+212611112222")
    mine = client.post("/v1/farms", json={"name": "Mine", "location": CASA}, headers=_h(owner)).json()
    theirs = client.post("/v1/farms", json={"name": "Theirs", "location": CASA}, headers=_h(other)).json()
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'manager')", theirs["id"], owner["user"]["id"])
    roles = {f["name"]: f["role"] for f in client.get("/v1/farms", headers=_h(owner)).json()}
    assert roles == {"Mine": "owner", "Theirs": "manager"} and mine["id"]


def test_given_a_second_owner_row_when_inserting_then_the_database_refuses_it(client):
    s = login(client)
    f = client.post("/v1/farms", json={"name": "F", "location": CASA}, headers=_h(s)).json()
    import uuid

    with pytest.raises(Exception):  # noqa: B017 - unique partial index on role = 'owner'
        sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2, 'owner')", f["id"], uuid.uuid4())

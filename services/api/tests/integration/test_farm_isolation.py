"""T006 - cross-farm access is a 404 identical to an unknown farm; insufficient role is 403 (FR-021)."""
import uuid

import pytest

from tests.helpers import auth, sql

IGNORED_HEADERS = {"date", "server", "x-request-id"}


def _call(client, token, method, path, body=None):
    return client.request(method, path, headers=auth(token), json=body)


def _shape(r):
    return (
        r.status_code,
        r.content,
        {k: v for k, v in r.headers.items() if k.lower() not in IGNORED_HEADERS},
    )


def _routes(farm, member, inv):
    f = f"/v1/farms/{farm}"
    return [
        ("GET", f, None),
        ("PATCH", f, {"name": "Renamed"}),
        ("GET", f"{f}/members", None),
        ("PATCH", f"{f}/members/{member}", {"role": "manager"}),
        ("DELETE", f"{f}/members/{member}", None),
        ("PUT", f"{f}/members/{member}/parcels", {"parcel_ids": []}),
        ("GET", f"{f}/invitations", None),
        ("POST", f"{f}/invitations", {"phone": "+212612345679", "role": "worker"}),
        ("DELETE", f"{f}/invitations/{inv}", None),
    ]


def _invitation(farm, owner, phone="+212612345679", role="worker"):
    inv = uuid.uuid4()
    sql(
        "INSERT INTO invitations (id, farm_id, phone_e164, role, status, invited_by, expires_at)"
        " VALUES ($1, $2, $3, $4, 'pending', $5, now() + interval '30 days')",
        inv, farm, phone, role, owner,
    )
    return inv


@pytest.fixture
def world(make_farm, token_for):
    owner, manager, worker, stranger = (uuid.uuid4() for _ in range(4))
    farm = make_farm({owner: "owner", manager: "manager", worker: "worker"})
    other_owner = uuid.uuid4()
    other = make_farm({other_owner: "owner"})
    return {
        "farm": farm, "other": other, "owner": owner, "manager": manager, "worker": worker,
        "stranger": stranger, "other_owner": other_owner, "token_for": token_for,
        "inv": _invitation(farm, owner), "other_inv": _invitation(other, other_owner, "+212612345680"),
    }


def test_given_a_member_when_reading_the_farm_then_the_route_exists_and_answers_200(client, world):
    r = _call(client, world["token_for"](world["owner"]), "GET", f"/v1/farms/{world['farm']}")
    assert r.status_code == 200


@pytest.mark.parametrize("idx", range(9))
def test_given_a_non_member_when_calling_any_farm_route_then_the_404_is_identical_to_an_unknown_farm(
    client, world, idx
):
    t = world["token_for"](world["stranger"])
    # positive control: the route is real for a member
    owner_r = _call(client, world["token_for"](world["owner"]), *_routes(world["farm"], world["worker"], world["inv"])[idx])
    assert owner_r.status_code not in (404, 405), owner_r.text
    real = _call(client, t, *_routes(world["farm"], world["worker"], world["inv"])[idx])
    ghost = _call(client, t, *_routes(uuid.uuid4(), world["worker"], world["inv"])[idx])
    assert real.status_code == 404
    real_shape, ghost_shape = _shape(real), _shape(ghost)
    assert real_shape[0] == ghost_shape[0] and real_shape[1] == ghost_shape[1]
    assert {k: v for k, v in real_shape[2].items() if k != "content-length"} == {
        k: v for k, v in ghost_shape[2].items() if k != "content-length"
    }


def test_given_a_member_of_another_farm_when_reading_this_farm_then_it_is_404_not_403(client, world):
    r = _call(client, world["token_for"](world["other_owner"]), "GET", f"/v1/farms/{world['farm']}")
    assert r.status_code == 404


@pytest.mark.parametrize(
    "role,idx",
    [("worker", 1), ("worker", 3), ("worker", 4), ("worker", 5), ("worker", 7), ("worker", 8),
     ("manager", 3), ("manager", 4), ("manager", 7), ("manager", 8)],
)
def test_given_a_member_with_insufficient_role_when_calling_a_restricted_route_then_403(
    client, world, role, idx
):
    user = world[role]
    method, path, body = _routes(world["farm"], world["worker"], world["inv"])[idx]
    assert _call(client, world["token_for"](world["owner"]), "GET", f"/v1/farms/{world['farm']}").status_code == 200
    r = _call(client, world["token_for"](user), method, path, body)
    assert r.status_code == 403


def test_given_an_invitation_of_another_farm_when_addressed_via_my_farm_then_404(client, world):
    t = world["token_for"](world["owner"])
    ok = _call(client, t, "DELETE", f"/v1/farms/{world['farm']}/invitations/{world['inv']}")
    assert ok.status_code == 204
    r = _call(client, t, "DELETE", f"/v1/farms/{world['farm']}/invitations/{world['other_inv']}")
    assert r.status_code == 404
    assert sql("SELECT status FROM invitations WHERE id = $1", world["other_inv"])[0][0] == "pending"


def test_given_a_member_of_another_farm_when_addressed_via_my_farm_then_404_and_nothing_changes(client, world):
    t = world["token_for"](world["owner"])
    r = _call(client, t, "PATCH", f"/v1/farms/{world['farm']}/members/{world['other_owner']}", {"role": "worker"})
    assert r.status_code == 404
    r = _call(client, t, "DELETE", f"/v1/farms/{world['farm']}/members/{world['other_owner']}")
    assert r.status_code == 404
    r = _call(client, t, "PUT", f"/v1/farms/{world['farm']}/members/{world['other_owner']}/parcels", {"parcel_ids": []})
    assert r.status_code == 404
    role = sql("SELECT role FROM farm_members WHERE farm_id=$1 AND user_id=$2", world["other"], world["other_owner"])
    assert role[0][0] == "owner"

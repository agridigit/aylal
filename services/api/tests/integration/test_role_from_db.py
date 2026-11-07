"""T008 - the role is read from the database on every request, never from the token (R6-A4, R6-A5)."""
import uuid

from tests.helpers import auth, op, sql


def _farm_get(client, token, farm):
    return client.get(f"/v1/farms/{farm}", headers=auth(token))


def _upload(client, token, farm):
    return client.post(
        "/v1/sync/upload", headers=auth(token),
        json={"ops": [op(farm, uuid.uuid4(), kind="put", fields={"title": "t"})]},
    )


def test_given_a_worker_token_when_the_member_is_promoted_to_manager_then_the_old_token_can_patch_the_farm(
    client, token_for, make_farm
):
    owner, user = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", user: "worker"})
    token = token_for(user)
    assert client.patch(f"/v1/farms/{farm}", headers=auth(token), json={"name": "X"}).status_code == 403
    sql("UPDATE farm_members SET role='manager' WHERE farm_id=$1 AND user_id=$2", farm, user)
    assert client.patch(f"/v1/farms/{farm}", headers=auth(token), json={"name": "X"}).status_code == 200


def test_given_a_manager_token_when_the_member_is_demoted_to_worker_then_the_old_token_is_refused_at_once(
    client, token_for, make_farm
):
    owner, user = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", user: "manager"})
    token = token_for(user)
    assert client.patch(f"/v1/farms/{farm}", headers=auth(token), json={"name": "X"}).status_code == 200
    sql("UPDATE farm_members SET role='worker' WHERE farm_id=$1 AND user_id=$2", farm, user)
    assert client.patch(f"/v1/farms/{farm}", headers=auth(token), json={"name": "Y"}).status_code == 403


def test_given_a_member_token_when_the_member_is_removed_then_the_farm_is_404_with_the_old_token(
    client, token_for, make_farm
):
    owner, user = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", user: "manager"})
    token = token_for(user)
    assert _farm_get(client, token, farm).status_code == 200
    sql("DELETE FROM farm_members WHERE farm_id=$1 AND user_id=$2", farm, user)
    assert _farm_get(client, token, farm).status_code == 404


def test_given_a_soft_removed_member_when_calling_with_the_old_token_then_the_farm_is_404(
    client, token_for, make_farm
):
    owner, user = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", user: "worker"})
    token = token_for(user)
    sql("UPDATE farm_members SET removed_at = now() WHERE farm_id=$1 AND user_id=$2", farm, user)
    assert _farm_get(client, token, farm).status_code == 404


def test_given_a_removed_member_when_uploading_with_the_old_token_then_nothing_is_written(
    client, token_for, make_farm
):
    owner, user = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", user: "manager"})
    token = token_for(user)
    assert _upload(client, token, farm).json()["results"][0]["status"] == "applied"
    sql("DELETE FROM farm_members WHERE farm_id=$1 AND user_id=$2", farm, user)
    r = _upload(client, token, farm)
    assert r.status_code in (403, 404) or r.json()["results"][0]["status"] == "rejected"
    assert sql("SELECT count(*) FROM trial_records WHERE farm_id=$1", farm)[0][0] == 1


def test_given_a_worker_token_when_the_member_becomes_manager_then_parcel_assignment_is_allowed(
    client, token_for, make_farm
):
    owner, user, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner", user: "worker", other: "worker"})
    token = token_for(user)
    url = f"/v1/farms/{farm}/members/{other}/parcels"
    assert client.put(url, headers=auth(token), json={"parcel_ids": []}).status_code == 403
    sql("UPDATE farm_members SET role='manager' WHERE farm_id=$1 AND user_id=$2", farm, user)
    assert client.put(url, headers=auth(token), json={"parcel_ids": []}).status_code == 200

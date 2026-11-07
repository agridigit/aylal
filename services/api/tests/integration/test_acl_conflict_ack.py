"""T040a - acknowledging a conflict is scoped to the conflict's farm (FR-018, cross-farm security)."""
import uuid

import pytest

from tests.helpers import auth, op, sql


@pytest.fixture
def conflict(client, token_for, make_farm, upload):
    owner, editor, viewer, stranger = (uuid.uuid4() for _ in range(4))
    farm = make_farm({owner: "owner", editor: "manager", viewer: "worker"})
    other_farm = make_farm({stranger: "owner"})
    rid = uuid.uuid4()
    t = token_for(owner)
    v1 = upload(t, [op(farm, rid, kind="put", fields={"title": "t"})])["results"][0]["server_version"]
    upload(t, [op(farm, rid, fields={"title": "A"}, base_version=v1)])
    upload(t, [op(farm, rid, fields={"title": "B"}, base_version=v1)])
    (c,) = sql("SELECT id FROM sync_conflicts WHERE record_id = $1", rid)
    assert other_farm != farm
    return {"id": c["id"], "owner": owner, "editor": editor, "viewer": viewer, "stranger": stranger}


def _ack(client, token, cid):
    return client.post(f"/v1/sync/conflicts/{cid}/acknowledge", headers=auth(token))


def _unacked(cid) -> bool:
    return sql("SELECT acknowledged_at FROM sync_conflicts WHERE id = $1", cid)[0][0] is None


@pytest.mark.parametrize("who", ["owner", "editor"])
def test_given_an_editor_or_owner_of_the_farm_when_acknowledging_then_204(
    who, client, token_for, conflict
) -> None:
    assert _ack(client, token_for(conflict[who]), conflict["id"]).status_code == 204
    assert not _unacked(conflict["id"])


def test_given_a_user_of_another_farm_when_acknowledging_then_404_identical_to_unknown_id(
    client, token_for, conflict
) -> None:
    t = token_for(conflict["stranger"])
    cross = _ack(client, t, conflict["id"])
    unknown = _ack(client, t, uuid.uuid4())
    assert cross.status_code == 404
    assert (cross.status_code, cross.json()) == (unknown.status_code, unknown.json())
    assert _unacked(conflict["id"])


def test_given_a_non_member_with_no_farm_when_acknowledging_then_404(
    client, token_for, conflict
) -> None:
    r = _ack(client, token_for(uuid.uuid4()), conflict["id"])
    assert r.status_code == 404
    assert _unacked(conflict["id"])


def test_given_a_viewer_of_the_right_farm_when_acknowledging_then_403_and_still_unacknowledged(
    client, token_for, conflict
) -> None:
    assert _ack(client, token_for(conflict["viewer"]), conflict["id"]).status_code == 403
    assert _unacked(conflict["id"])


def test_given_no_token_when_acknowledging_then_401_and_still_unacknowledged(
    client, conflict
) -> None:
    r = client.post(f"/v1/sync/conflicts/{conflict['id']}/acknowledge")
    assert r.status_code == 401
    assert _unacked(conflict["id"])


# --- F1 non-regression (T007): acknowledging a conflict with the new role names ---


@pytest.fixture
def conflict_f1(client, token_for, make_farm, upload):
    owner, manager, worker = (uuid.uuid4() for _ in range(3))
    farm = make_farm({owner: "owner", manager: "manager", worker: "worker"})
    rid = uuid.uuid4()
    t = token_for(owner)
    v1 = upload(t, [op(farm, rid, kind="put", fields={"title": "t"})])["results"][0]["server_version"]
    upload(t, [op(farm, rid, fields={"title": "A"}, base_version=v1)])
    upload(t, [op(farm, rid, fields={"title": "B"}, base_version=v1)])
    (c,) = sql("SELECT id FROM sync_conflicts WHERE record_id = $1", rid)
    return {"id": c["id"], "manager": manager, "worker": worker}


def test_given_a_manager_when_acknowledging_a_conflict_then_it_is_204(client, token_for, conflict_f1):
    assert _ack(client, token_for(conflict_f1["manager"]), conflict_f1["id"]).status_code == 204


def test_given_a_worker_when_acknowledging_a_conflict_then_it_is_403_and_stays_open(client, token_for, conflict_f1):
    assert _ack(client, token_for(conflict_f1["worker"]), conflict_f1["id"]).status_code == 403
    assert _unacked(conflict_f1["id"])

"""T038 - access control by farm and role on synchronised writes (FR-018, R8)."""
import uuid

import pytest

from tests.helpers import auth, op, record_row


def _put(farm, rid=None, title="t"):
    return op(farm, rid or uuid.uuid4(), kind="put", fields={"title": title})


def test_given_a_non_member_when_uploading_to_a_farm_then_the_op_is_rejected_as_forbidden(
    client, token_for, make_farm, upload
) -> None:
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({owner: "owner"})
    rid = uuid.uuid4()
    res = upload(token_for(stranger), [_put(farm, rid)])["results"][0]
    assert res["status"] == "rejected"
    assert res["error"]["code"] == "forbidden"
    assert record_row(rid) is None


def test_given_a_viewer_when_writing_then_the_op_is_rejected_and_nothing_is_stored(
    client, token_for, make_farm, upload
) -> None:
    viewer = uuid.uuid4()
    farm = make_farm({viewer: "viewer"})
    rid = uuid.uuid4()
    res = upload(token_for(viewer), [_put(farm, rid)])["results"][0]
    assert (res["status"], res["error"]["code"]) == ("rejected", "forbidden")
    assert record_row(rid) is None


@pytest.mark.parametrize("role", ["editor", "owner"])
def test_given_an_editor_or_owner_when_writing_then_the_op_is_applied(
    role, client, token_for, make_farm, upload
) -> None:
    user = uuid.uuid4()
    farm = make_farm({user: role})
    rid = uuid.uuid4()
    res = upload(token_for(user), [_put(farm, rid)])["results"][0]
    assert res["status"] == "applied"
    assert record_row(rid) is not None


def test_given_a_member_of_farm_a_when_writing_to_farm_b_then_the_op_is_forbidden(
    client, token_for, make_farm, upload
) -> None:
    user = uuid.uuid4()
    make_farm({user: "owner"})
    other = make_farm({uuid.uuid4(): "owner"})
    res = upload(token_for(user), [_put(other)])["results"][0]
    assert (res["status"], res["error"]["code"]) == ("rejected", "forbidden")


def test_given_farm_members_when_a_client_tries_to_write_it_then_the_batch_is_malformed(
    client, token_for, make_farm
) -> None:
    owner = uuid.uuid4()
    farm = make_farm({owner: "owner"})
    bad = op(farm, uuid.uuid4(), kind="put", fields={"role": "owner"})
    bad["table"] = "farm_members"
    r = client.post("/v1/sync/upload", json={"ops": [bad]}, headers=auth(token_for(owner)))
    assert r.status_code == 422


def test_given_a_forbidden_op_in_a_batch_then_the_allowed_ops_still_apply(
    client, token_for, make_farm, upload
) -> None:
    user = uuid.uuid4()
    mine = make_farm({user: "editor"})
    theirs = make_farm({uuid.uuid4(): "owner"})
    res = upload(token_for(user), [_put(theirs), _put(mine)])["results"]
    assert [r["status"] for r in res] == ["rejected", "applied"]


# --- F1 non-regression (T007): same ACL semantics after editor->manager, viewer->worker ---


def test_given_a_worker_when_writing_then_the_op_is_rejected_and_nothing_is_stored(
    client, token_for, make_farm, upload
) -> None:
    worker = uuid.uuid4()
    farm = make_farm({worker: "worker"})
    rid = uuid.uuid4()
    res = upload(token_for(worker), [_put(farm, rid)])["results"][0]
    assert (res["status"], res["error"]["code"]) == ("rejected", "forbidden")
    assert record_row(rid) is None


@pytest.mark.parametrize("role", ["manager", "owner"])
def test_given_a_manager_or_owner_when_writing_then_the_op_is_applied(
    role, client, token_for, make_farm, upload
) -> None:
    user = uuid.uuid4()
    farm = make_farm({user: role})
    rid = uuid.uuid4()
    assert upload(token_for(user), [_put(farm, rid)])["results"][0]["status"] == "applied"
    assert record_row(rid) is not None


def test_given_f0_roles_in_the_database_when_migrated_then_editor_is_manager_and_viewer_is_worker() -> None:
    from tests.helpers import sql

    allowed = sql(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c"
        " JOIN pg_class t ON t.oid = c.conrelid WHERE t.relname = 'farm_members' AND c.contype = 'c'"
    )
    text = " ".join(r[0] for r in allowed)
    assert "manager" in text and "worker" in text
    assert "editor" not in text and "viewer" not in text

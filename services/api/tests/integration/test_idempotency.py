"""T039 - replayed op_id returns the recorded result, never re-applies (FR-013, AC3.2)."""
import uuid

from tests.helpers import op, record_row, sql


def test_given_an_applied_op_when_replayed_then_the_recorded_result_is_returned_as_duplicate(
    client, token_for, make_farm, upload
) -> None:
    user, rid, oid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    farm = make_farm({user: "editor"})
    token = token_for(user)
    put = op(farm, rid, kind="put", fields={"title": "once"}, op_id=oid)
    first = upload(token, [put])["results"][0]
    again = upload(token, [put])["results"][0]
    assert first["status"] == "applied"
    assert again["status"] == "duplicate"
    assert again["server_version"] == first["server_version"]
    assert len(sql("SELECT 1 FROM applied_ops WHERE op_id = $1", oid)) == 1
    assert record_row(rid)["server_version"] == first["server_version"]


def test_given_a_replayed_patch_when_sent_twice_then_the_version_does_not_grow(
    client, token_for, make_farm, upload
) -> None:
    user, rid = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({user: "editor"})
    token = token_for(user)
    v = upload(token, [op(farm, rid, kind="put", fields={"title": "a"})])["results"][0]["server_version"]
    patch = op(farm, rid, fields={"title": "b"}, base_version=v)
    upload(token, [patch])
    after_first = record_row(rid)["server_version"]
    upload(token, [patch])
    assert record_row(rid)["server_version"] == after_first


def test_given_a_cut_connection_mid_upload_when_the_whole_batch_is_resent_then_no_duplicate(
    client, token_for, make_farm, upload
) -> None:
    user = uuid.uuid4()
    farm = make_farm({user: "editor"})
    token = token_for(user)
    ids = [uuid.uuid4() for _ in range(5)]
    batch = [op(farm, i, kind="put", fields={"title": f"r{n}"}) for n, i in enumerate(ids)]
    upload(token, batch[:3])  # response lost: the client never learned it
    res = upload(token, batch)["results"]
    assert [r["status"] for r in res] == ["duplicate"] * 3 + ["applied"] * 2
    assert sql("SELECT count(*) AS n FROM trial_records")[0]["n"] == 5
    assert sql("SELECT count(*) AS n FROM applied_ops")[0]["n"] == 5

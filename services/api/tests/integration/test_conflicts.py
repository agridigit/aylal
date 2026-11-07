"""T040 - same field edited by two devices: arrival order, logged, no silent loss (AC3.4, FR-015)."""
import uuid

from tests.helpers import op, record_row, sql


def _two_device_conflict(token_for, make_farm, upload, clock_a=None, clock_b=None):
    user_a, user_b, rid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    farm = make_farm({user_a: "editor", user_b: "editor"})
    ta, tb = token_for(user_a), token_for(user_b)
    v1 = upload(ta, [op(farm, rid, kind="put", fields={"title": "base", "note": "n"})])["results"][0][
        "server_version"
    ]
    a = upload(ta, [op(farm, rid, fields={"title": "from A"}, base_version=v1, device_clock=clock_a)])
    b = upload(tb, [op(farm, rid, fields={"title": "from B"}, base_version=v1, device_clock=clock_b)])
    return rid, v1, user_b, a["results"][0], b["results"][0]


def test_given_two_devices_editing_one_field_when_both_sync_then_last_arrival_wins_and_is_logged(
    client, token_for, make_farm, upload
) -> None:
    rid, v1, user_b, a, b = _two_device_conflict(token_for, make_farm, upload)
    assert a["status"] == "applied"
    assert b["status"] == "conflict_logged"
    row = record_row(rid)
    assert row["title"] == "from B"
    assert row["has_conflict"] is True
    (c,) = sql("SELECT * FROM sync_conflicts WHERE record_id = $1", rid)
    assert c["field"] == "title"
    assert c["discarded_value"] in ('"from A"', "from A")  # jsonb text
    assert c["kept_value"] in ('"from B"', "from B")
    assert c["discarded_by"] == user_b
    assert c["base_version"] == v1
    assert c["server_version"] == b["server_version"]
    assert c["acknowledged_at"] is None


def test_given_a_conflict_when_other_fields_changed_then_they_merge_without_conflict(
    client, token_for, make_farm, upload
) -> None:
    user, rid = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({user: "editor"})
    t = token_for(user)
    v1 = upload(t, [op(farm, rid, kind="put", fields={"title": "t", "note": "n"})])["results"][0][
        "server_version"
    ]
    upload(t, [op(farm, rid, fields={"title": "t2"}, base_version=v1)])
    res = upload(t, [op(farm, rid, fields={"note": "n2"}, base_version=v1)])["results"][0]
    assert res["status"] == "applied"
    row = record_row(rid)
    assert (row["title"], row["note"], row["has_conflict"]) == ("t2", "n2", False)
    assert sql("SELECT 1 FROM sync_conflicts") == []


def test_given_skewed_device_clocks_when_resolving_then_the_outcome_is_unchanged(
    client, token_for, make_farm, upload
) -> None:
    rid, *_ = _two_device_conflict(
        token_for, make_farm, upload, clock_a="2099-01-01T00:00:00Z", clock_b="1970-01-01T00:00:00Z"
    )
    assert record_row(rid)["title"] == "from B"
    assert len(sql("SELECT 1 FROM sync_conflicts WHERE record_id = $1", rid)) == 1


def test_given_a_conflict_when_acknowledged_then_has_conflict_is_cleared(
    client, token_for, make_farm, upload
) -> None:
    from tests.helpers import auth

    rid, *_ = _two_device_conflict(token_for, make_farm, upload)
    (c,) = sql("SELECT id, farm_id FROM sync_conflicts WHERE record_id = $1", rid)
    (member,) = sql("SELECT user_id FROM farm_members WHERE farm_id = $1 LIMIT 1", c["farm_id"])
    r = client.post(
        f"/v1/sync/conflicts/{c['id']}/acknowledge", headers=auth(token_for(member["user_id"]))
    )
    assert r.status_code == 204
    assert record_row(rid)["has_conflict"] is False
    assert sql("SELECT acknowledged_at FROM sync_conflicts WHERE id = $1", c["id"])[0][0] is not None

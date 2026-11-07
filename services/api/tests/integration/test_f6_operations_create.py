"""T033 - R1-A1, R1-A3, R1-A5: minimal creation, the 9 types, prorata allocation, paginated chronological journal."""
import datetime as dt
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, op_body, world  # noqa: F401

TYPES = ("phyto", "fertilization", "irrigation", "tillage", "sowing_planting", "pruning", "weeding", "harvest", "other")


def create(client, token_for, who, farm, body):
    return client.post(f"/v1/farms/{farm}/operations", headers=auth(token_for(who)), json=body)


def set_area(parcel, ha):
    sql("UPDATE parcels SET area_calc_ha=$2, area_declared_ha=$2 WHERE id=$1", parcel, ha)


def test_given_only_type_parcel_and_date_when_recording_then_the_operation_is_created(client, token_for, world):
    w = world
    body = {"id": str(uuid.uuid4()), "type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]}
    r = create(client, token_for, w["owner"], w["farm_a"], body)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["id"] == body["id"] and out["type"] == "irrigation" and out["status"] == "validated"
    assert out["author_id"] == str(w["owner"]) and [p["parcel_id"] for p in out["parcels"]] == [str(w["a1"])]


@pytest.mark.parametrize("type_", TYPES)
def test_given_each_of_the_nine_types_when_recording_then_it_is_accepted_and_listed(client, token_for, world, type_):
    w = world
    r = create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"]], type=type_))
    assert r.status_code == 201, r.text
    listed = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"]))).json()["items"]
    assert [i["type"] for i in listed] == [type_]


def test_given_a_tenth_type_or_a_missing_required_field_when_recording_then_422_and_nothing_is_written(client, token_for, world):
    w = world
    for body in (op_body([w["a1"]], type="spraying"), op_body([], type="other")):
        assert create(client, token_for, w["owner"], w["farm_a"], body).status_code == 422
    for missing in ("type", "performed_on", "parcel_ids"):
        body = op_body([w["a1"]])
        del body[missing]
        assert create(client, token_for, w["owner"], w["farm_a"], body).status_code == 422, missing
    assert sql("SELECT count(*) FROM operations")[0][0] == 0


def test_given_a_quantity_over_several_parcels_when_recording_then_it_is_split_by_area_and_adds_up(client, token_for, world):
    w = world
    set_area(w["a1"], 1)
    set_area(w["a2"], 3)
    r = create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"], w["a2"]], type="fertilization", quantity_total=10, quantity_unit="kg"))
    assert r.status_code == 201, r.text
    shares = {p["parcel_id"]: p["allocated_quantity"] for p in r.json()["parcels"]}
    assert shares == {str(w["a1"]): 2.5, str(w["a2"]): 7.5}
    assert r.json()["quantity_total"] == 10 and r.json()["quantity_unit"] == "kg"


def test_given_an_uneven_split_when_recording_then_the_shares_always_add_up_to_the_total(client, token_for, world):
    w = world
    for p in (w["a1"], w["a2"]):
        set_area(p, 1)
    r = create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"], w["a2"]], type="other", quantity_total=0.001 * 7, quantity_unit="kg"))
    assert round(sum(p["allocated_quantity"] for p in r.json()["parcels"]), 3) == 0.007


def test_given_the_same_client_id_when_recording_twice_then_one_operation_exists_and_the_second_answer_is_200(client, token_for, world):
    w = world
    body = op_body([w["a1"]])
    first = create(client, token_for, w["owner"], w["farm_a"], body)
    second = create(client, token_for, w["owner"], w["farm_a"], body)
    assert (first.status_code, second.status_code) == (201, 200) and first.json()["id"] == second.json()["id"]
    assert sql("SELECT count(*) FROM operations WHERE id=$1", uuid.UUID(body["id"]))[0][0] == 1


def test_given_an_id_used_in_another_farm_when_recording_then_404_and_that_operation_is_untouched(client, token_for, world):
    w = world
    body = op_body([w["b1"]])
    assert create(client, token_for, w["owner_b"], w["farm_b"], body).status_code == 201
    assert create(client, token_for, w["owner"], w["farm_a"], {**body, "parcel_ids": [str(w["a1"])]}).status_code == 404
    assert sql("SELECT farm_id FROM operations WHERE id=$1", uuid.UUID(body["id"]))[0][0] == w["farm_b"]


def test_given_operations_on_several_dates_when_opening_the_journal_then_they_come_in_chronological_order_with_type_parcel_and_date(client, token_for, world):
    w = world
    days = [TODAY - dt.timedelta(days=d) for d in (3, 0, 5, 1)]
    for day in days:
        create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"]], performed_on=day.isoformat()))
    items = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"]))).json()["items"]
    assert [i["performed_on"] for i in items] == [d.isoformat() for d in sorted(days, reverse=True)]
    assert all(i["type"] == "irrigation" and i["parcels"][0]["parcel_id"] == str(w["a1"]) for i in items)


def test_given_more_operations_than_a_page_when_paginating_then_every_operation_is_seen_once(client, token_for, world):
    w = world
    ids = {create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"]], performed_on=(TODAY - dt.timedelta(days=i % 3)).isoformat())).json()["id"] for i in range(7)}
    seen, cursor = [], None
    for _ in range(10):
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        page = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), params=params).json()
        assert len(page["items"]) <= 3
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == sorted(ids) and len(seen) == len(set(seen)) == 7


def test_given_filters_when_listing_then_type_parcel_and_status_narrow_the_journal(client, token_for, world):
    w = world
    create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"]], type="pruning"))
    create(client, token_for, w["owner"], w["farm_a"], op_body([w["a2"]], type="weeding"))
    h = auth(token_for(w["owner"]))
    base = f"/v1/farms/{w['farm_a']}/operations"
    assert [i["type"] for i in client.get(base, headers=h, params={"type": "pruning"}).json()["items"]] == ["pruning"]
    assert [i["type"] for i in client.get(base, headers=h, params={"parcel_id": str(w["a2"])}).json()["items"]] == ["weeding"]
    assert len(client.get(base, headers=h, params={"status": "validated"}).json()["items"]) == 2


def test_given_an_unknown_status_filter_or_a_bad_cursor_when_listing_then_422(client, token_for, world):
    h = auth(token_for(world["owner"]))
    base = f"/v1/farms/{world['farm_a']}/operations"
    assert client.get(base, headers=h, params={"cursor": "!!"}).status_code == 422
    assert client.get(base, headers=h, params={"status": "bogus"}).status_code == 422
    assert client.get(base, headers=h, params={"limit": 201}).status_code == 422


def test_given_an_operation_a_parcel_that_does_not_exist_or_is_archived_when_recording_then_404(client, token_for, world):
    w = world
    assert create(client, token_for, w["owner"], w["farm_a"], op_body([uuid.uuid4()])).status_code == 404
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    assert create(client, token_for, w["owner"], w["farm_a"], op_body([w["a1"]])).status_code == 404

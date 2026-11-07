"""T055 - R3-A4: the DAR is recomputed from registry_current; workers see only assigned, non archived parcels."""
import datetime as dt

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, op_body, world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product, crops, grow


@pytest.fixture
def stock(world):
    (cid, slug), = crops(1)
    grow(world["farm_a"], world["a1"], cid)
    version = add_catalog()
    return dict(world, version=version, slug=slug,
                p21=add_product(version, "Vingt", [dict(crop_slug=slug, max_dose=5, dar_days=21)]),
                p7=add_product(version, "Sept", [dict(crop_slug=slug, max_dose=5, dar_days=7)]))


def treat(client, token_for, s, product, who="owner", on=None, parcel="a1"):
    return client.post(f"/v1/farms/{s['farm_a']}/operations", headers=auth(token_for(s[who])),
                       json=op_body([s[parcel]], type="phyto", product_id=str(product), dose=1, dose_unit="L/ha",
                                    **({"performed_on": on.isoformat()} if on else {})))


def harvest(client, token_for, s, who="owner", parcel="a1", farm="farm_a"):
    return client.get(f"/v1/farms/{s[farm]}/fields/{s[parcel]}/earliest-harvest", headers=auth(token_for(s[who])))


def test_given_a_treatment_with_a_21_day_interval_then_the_earliest_harvest_is_d_plus_21(client, token_for, stock):
    treat(client, token_for, stock, stock["p21"])
    body = harvest(client, token_for, stock).json()
    assert body["date"] == (TODAY + dt.timedelta(days=21)).isoformat()
    assert body["limiting_product"] == "Vingt" and body["harvestable_now"] is False and body["unknown_dar"] is False


def test_given_several_treatments_then_the_longest_remaining_interval_applies(client, token_for, stock):
    treat(client, token_for, stock, stock["p7"])
    treat(client, token_for, stock, stock["p21"], on=TODAY - dt.timedelta(days=2))
    assert harvest(client, token_for, stock).json()["date"] == (TODAY + dt.timedelta(days=19)).isoformat()


def test_given_no_treatment_then_the_parcel_is_harvestable_now(client, token_for, stock):
    body = harvest(client, token_for, stock).json()
    assert body["date"] is None and body["harvestable_now"] is True


def test_given_a_correction_of_the_product_then_the_date_is_recomputed(client, token_for, stock):
    s = stock
    r = treat(client, token_for, s, s["p21"])
    fixed = client.patch(f"/v1/farms/{s['farm_a']}/operations/{r.json()['id']}", headers=auth(token_for(s["owner"])), json={"product_id": str(s["p7"])})
    assert fixed.status_code == 200, fixed.text
    assert harvest(client, token_for, s).json()["date"] == (TODAY + dt.timedelta(days=7)).isoformat()


def test_given_a_cancelled_treatment_then_it_no_longer_limits_the_harvest_but_the_registry_keeps_both_rows(client, token_for, stock):
    s = stock
    r = treat(client, token_for, s, s["p21"])
    assert client.post(f"/v1/farms/{s['farm_a']}/operations/{r.json()['id']}/cancel", headers=auth(token_for(s["owner"]))).status_code == 200
    body = harvest(client, token_for, s).json()
    assert body["date"] is None and body["harvestable_now"] is True
    assert sorted(x[0] for x in sql("SELECT entry_kind FROM registry_entries WHERE operation_id=$1", __import__("uuid").UUID(r.json()["id"]))) == ["application", "reversal"]


def test_given_a_planned_treatment_then_it_does_not_limit_the_harvest_until_it_is_done(client, token_for, stock):
    s = stock
    r = treat(client, token_for, s, s["p21"], on=TODAY + dt.timedelta(days=2))
    assert r.json()["status"] == "planned"
    assert harvest(client, token_for, s).json()["date"] is None
    assert client.post(f"/v1/farms/{s['farm_a']}/operations/{r.json()['id']}/done", headers=auth(token_for(s["owner"]))).status_code == 200
    assert harvest(client, token_for, s).json()["date"] is not None


def test_given_an_unknown_interval_then_it_is_flagged(client, token_for, stock):
    s = stock
    r = client.post(f"/v1/farms/{s['farm_a']}/operations", headers=auth(token_for(s["owner"])),
                    json=op_body([s["a1"]], type="phyto", free_product_name="Maison", dose=1, dose_unit="L/ha"))
    assert r.status_code == 201
    assert harvest(client, token_for, s).json()["unknown_dar"] is True


def test_given_a_worker_on_an_assigned_parcel_then_the_date_includes_treatments_of_other_people(client, token_for, stock):
    s = stock
    treat(client, token_for, s, s["p21"], who="manager")
    assert harvest(client, token_for, s, who="worker").json()["date"] == harvest(client, token_for, s).json()["date"]


def test_given_a_worker_when_the_parcel_is_unassigned_or_archived_then_404_while_staff_still_read_it(client, token_for, stock):
    s = stock
    assert harvest(client, token_for, s, who="worker", parcel="a2").status_code == 404
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", s["a1"])
    assert harvest(client, token_for, s, who="worker").status_code == 404
    assert harvest(client, token_for, s, who="manager").status_code == 200


def test_given_a_parcel_of_another_farm_then_404_with_the_same_body_as_an_unknown_parcel(client, token_for, stock):
    s = stock
    foreign = harvest(client, token_for, s, parcel="b1")
    unknown = client.get(f"/v1/farms/{s['farm_a']}/fields/{__import__('uuid').uuid4()}/earliest-harvest", headers=auth(token_for(s["owner"])))
    assert foreign.status_code == unknown.status_code == 404 and foreign.json() == unknown.json()
    other_farm = harvest(client, token_for, s, who="outsider")
    assert other_farm.status_code == 404 and other_farm.json() == unknown.json()


def test_given_no_token_then_401(client, stock):
    assert client.get(f"/v1/farms/{stock['farm_a']}/fields/{stock['a1']}/earliest-harvest").status_code == 401

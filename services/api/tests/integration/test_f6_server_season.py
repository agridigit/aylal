"""Review finding 3: the campaign is derived by the server (active season of each parcel); a client season_id is only checked."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_season
from tests.integration._f6 import TODAY, op_body, sync_op, world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product, codes, crops, grow


@pytest.fixture
def stock(world):
    (tomato_id, tomato), (olive_id, _) = crops(2)
    w = world
    s_a1, s_a2 = grow(w["farm_a"], w["a1"], tomato_id), grow(w["farm_a"], w["a2"], olive_id)
    s_b1 = grow(w["farm_b"], w["b1"], tomato_id)
    product = add_product(add_catalog(), "Cuprex", [dict(crop_slug=tomato, max_dose=2, dose_unit="L/ha", dar_days=7, max_applications=2)])
    return dict(w, product=product, tomato_id=tomato_id, s_a1=s_a1, s_a2=s_a2, s_b1=s_b1)


def phyto(s, **kw):
    return op_body([s["a1"]], type="phyto", product_id=str(s["product"]), dose=1, dose_unit="L/ha", **kw)


def rest(client, token_for, s, body):
    return client.post(f"/v1/farms/{s['farm_a']}/operations", headers=auth(token_for(s["owner"])), json=body)


def fill(client, token_for, s, n=2):
    for _ in range(n):
        assert rest(client, token_for, s, phyto(s)).status_code == 201


def line_codes(out):
    return codes(next(p for p in out["parcels"] if p["parcel_id"])["warnings"])


def registry_seasons(op_id):
    return {r["parcel_id"]: r["season_id"] for r in sql("SELECT parcel_id, season_id FROM registry_entries WHERE operation_id=$1", uuid.UUID(op_id))}


def _foreign(s):
    return {"other_parcel": s["s_a2"], "other_farm": s["s_b1"], "unknown": uuid.uuid4()}


@pytest.mark.parametrize("kind", ["other_parcel", "other_farm", "unknown"])
def test_given_a_season_of_another_parcel_or_farm_or_unknown_when_recording_over_the_cap_then_it_is_refused_as_invalid_season(client, token_for, stock, kind):
    s = stock
    fill(client, token_for, s)
    r = rest(client, token_for, s, phyto(s, season_id=str(_foreign(s)[kind])))
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "invalid_season"
    assert sql("SELECT count(*) FROM registry_entries WHERE product_id=$1", s["product"])[0][0] == 2


def test_given_no_season_id_when_recording_then_the_server_uses_the_active_season_for_the_count_and_the_registry_line(client, token_for, stock):
    s = stock
    fill(client, token_for, s)
    r = rest(client, token_for, s, phyto(s))
    assert r.status_code == 201, r.text
    assert line_codes(r.json()) == ["max_applications_reached"]
    assert registry_seasons(r.json()["id"]) == {s["a1"]: s["s_a1"]}


def test_given_a_valid_season_id_when_recording_then_the_same_season_is_counted_and_registered(client, token_for, stock):
    s = stock
    fill(client, token_for, s)
    r = rest(client, token_for, s, phyto(s, season_id=str(s["s_a1"])))
    assert r.status_code == 201, r.text
    assert line_codes(r.json()) == ["max_applications_reached"]
    assert registry_seasons(r.json()["id"]) == {s["a1"]: s["s_a1"]}


def test_given_an_empty_ended_season_of_the_same_parcel_when_recording_over_the_cap_then_the_cap_warning_still_applies(client, token_for, stock):
    s = stock
    fill(client, token_for, s)
    old = uuid.uuid4()
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, ended_at) VALUES ($1,$2,$3,$4,current_date - 400,current_date - 200)",
        old, s["farm_a"], s["a1"], s["tomato_id"])
    r = rest(client, token_for, s, phyto(s, season_id=str(old)))
    assert r.status_code in (201, 422), r.text
    if r.status_code == 201:
        assert line_codes(r.json()) == ["max_applications_reached"]
        assert registry_seasons(r.json()["id"]) == {s["a1"]: s["s_a1"]}


def test_given_several_parcels_when_recording_then_each_registry_line_carries_the_season_of_its_own_parcel(client, token_for, stock):
    s = stock
    r = rest(client, token_for, s, op_body([s["a1"], s["a2"]], type="phyto", product_id=str(s["product"]), dose=1, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    assert registry_seasons(r.json()["id"]) == {s["a1"]: s["s_a1"], s["a2"]: s["s_a2"]}


def _upload(client, token_for, s, extra):
    rid = uuid.uuid4()
    fields = {"type": "phyto", "performed_on": TODAY.isoformat(), "parcel_ids": [str(s["a1"])], "product_id": str(s["product"]),
              "dose": 1, "dose_unit": "L/ha", **extra}
    r = client.post("/v1/sync/upload", headers=auth(token_for(s["owner"])), json={"ops": [sync_op("operations", s["farm_a"], rid, fields)]})
    assert r.status_code == 200, r.text
    return rid, r.json()["results"][0]


@pytest.mark.parametrize("kind", ["other_parcel", "other_farm", "unknown"])
def test_given_a_foreign_season_in_a_sync_upload_when_applied_then_the_operation_is_rejected_and_nothing_is_registered(client, token_for, stock, kind):
    s = stock
    fill(client, token_for, s)
    rid, res = _upload(client, token_for, s, {"season_id": str(_foreign(s)[kind])})
    assert res["status"] == "rejected", res
    assert sql("SELECT count(*) FROM operations WHERE id=$1", rid)[0][0] == 0
    assert sql("SELECT count(*) FROM registry_entries WHERE product_id=$1", s["product"])[0][0] == 2


def test_given_no_season_in_a_sync_upload_when_applied_then_the_server_season_is_counted_and_registered(client, token_for, stock):
    s = stock
    fill(client, token_for, s)
    rid, res = _upload(client, token_for, s, {})
    assert res["status"] != "rejected", res
    assert registry_seasons(str(rid)) == {s["a1"]: s["s_a1"]}
    row = sql("SELECT warnings FROM registry_entries WHERE operation_id=$1", rid)[0]
    assert "max_applications_reached" in str(row["warnings"])

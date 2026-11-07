"""T043 - R2-A1, R2-A3 to R2-A7: the server recomputes phyto warnings; they never block and are kept in the registry."""
import json
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, op_body, world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product, codes, crops, grow


@pytest.fixture
def stock(world):
    (tomato_id, tomato), (olive_id, olive) = crops(2)
    version = add_catalog()
    w = world
    grow(w["farm_a"], w["a1"], tomato_id)
    grow(w["farm_a"], w["a2"], olive_id)
    product = add_product(version, "Cuprex", [dict(crop_slug=tomato, max_dose=2, dose_unit="L/ha", dar_days=7, max_applications=2)])
    return dict(w, version=version, tomato=tomato, olive=olive, product=product, tomato_id=tomato_id)


def post(client, token_for, who, farm, body):
    return client.post(f"/v1/farms/{farm}/operations", headers=auth(token_for(who)), json=body)


def phyto(parcels, product, **kw):
    return op_body(parcels, type="phyto", product_id=str(product), **kw)


def parcel_codes(out, parcel):
    line = next(p for p in out["parcels"] if p["parcel_id"] == str(parcel))
    return codes(line["warnings"])


def test_given_a_dose_above_the_registered_maximum_when_recording_then_a_warning_is_returned_and_the_treatment_is_recorded(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=2.5, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    assert parcel_codes(r.json(), s["a1"]) == ["dose_above_max"]


def test_given_a_dose_in_another_convertible_unit_when_recording_then_the_comparison_uses_the_converted_dose(client, token_for, stock):
    s = stock
    over = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=2500, dose_unit="mL/ha"))
    ok = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=1500, dose_unit="mL/ha"))
    assert parcel_codes(over.json(), s["a1"]) == ["dose_above_max"]
    assert parcel_codes(ok.json(), s["a1"]) == []


def test_given_a_product_not_authorised_on_the_crop_when_recording_then_a_warning_is_returned_and_the_treatment_is_recorded(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a2"]], s["product"], dose=1, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    assert parcel_codes(r.json(), s["a2"]) == ["not_authorized_for_crop"]


def test_given_parcels_of_different_crops_when_recording_then_the_controls_apply_parcel_by_parcel(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"], s["a2"]], s["product"], dose=1, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    assert parcel_codes(r.json(), s["a1"]) == []
    assert parcel_codes(r.json(), s["a2"]) == ["not_authorized_for_crop"]
    for w in r.json()["parcels"][0]["warnings"] + r.json()["parcels"][1]["warnings"]:
        assert w["parcel_id"] in (str(s["a1"]), str(s["a2"]))


def test_given_the_maximum_number_of_applications_per_campaign_when_recording_again_then_a_warning_is_returned_without_blocking(client, token_for, stock):
    s = stock
    season = sql("SELECT id FROM seasons WHERE field_id=$1", s["a1"])[0][0]
    outs = [post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=1, dose_unit="L/ha", season_id=str(season)))
            for _ in range(3)]
    assert [o.status_code for o in outs] == [201, 201, 201]
    assert [parcel_codes(o.json(), s["a1"]) for o in outs] == [[], [], ["max_applications_reached"]]


def test_given_applications_of_another_product_or_campaign_when_counting_then_they_do_not_count(client, token_for, stock):
    s = stock
    other = add_product(s["version"], "Autrex", [dict(crop_slug=s["tomato"], max_dose=2, dar_days=3, max_applications=2)])
    season = sql("SELECT id FROM seasons WHERE field_id=$1", s["a1"])[0][0]
    for _ in range(3):
        post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], other, dose=1, dose_unit="L/ha", season_id=str(season)))
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=1, dose_unit="L/ha", season_id=str(season)))
    assert parcel_codes(r.json(), s["a1"]) == []


def test_given_a_cancelled_application_when_counting_then_it_does_not_count(client, token_for, stock):
    s = stock
    season = sql("SELECT id FROM seasons WHERE field_id=$1", s["a1"])[0][0]
    first = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=1, dose_unit="L/ha", season_id=str(season)))
    post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=1, dose_unit="L/ha", season_id=str(season)))
    assert client.post(f"/v1/farms/{s['farm_a']}/operations/{first.json()['id']}/cancel", headers=auth(token_for(s["owner"]))).status_code == 200
    third = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=1, dose_unit="L/ha", season_id=str(season)))
    assert parcel_codes(third.json(), s["a1"]) == []


def test_given_a_product_without_known_interval_when_recording_then_dar_unknown_is_returned(client, token_for, stock):
    s = stock
    no_dar = add_product(s["version"], "Sansdar", [dict(crop_slug=s["tomato"], max_dose=2, dar_days=None)])
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], no_dar, dose=1, dose_unit="L/ha"))
    assert parcel_codes(r.json(), s["a1"]) == ["dar_unknown"]


def test_given_a_free_product_when_recording_then_it_is_flagged_unchecked_and_not_controlled_against_the_catalogue(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], op_body([s["a2"]], type="phyto", free_product_name="Maison", dose=99, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    assert parcel_codes(r.json(), s["a2"]) == ["free_product_unchecked"]
    row = sql("SELECT is_free_product, product_name, warnings FROM registry_entries WHERE operation_id=$1", uuid.UUID(r.json()["id"]))[0]
    assert row["is_free_product"] is True and row["product_name"] == "Maison"


def test_given_no_product_and_no_dose_when_recording_a_phyto_treatment_then_it_is_recorded_without_warning(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], op_body([s["a1"]], type="phyto"))
    assert r.status_code == 201, r.text
    assert parcel_codes(r.json(), s["a1"]) == []


def test_given_warnings_sent_by_the_client_when_recording_then_they_are_never_believed(client, token_for, stock):
    s = stock
    body = phyto([s["a1"]], s["product"], dose=1, dose_unit="L/ha", warnings=[{"code": "dose_above_max"}])
    r = post(client, token_for, s["owner"], s["farm_a"], body)
    assert r.status_code in (201, 422), r.text
    if r.status_code == 201:
        assert parcel_codes(r.json(), s["a1"]) == []
    # a client hiding a real warning does not remove it either
    again = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=5, dose_unit="L/ha"))
    assert parcel_codes(again.json(), s["a1"]) == ["dose_above_max"]


def test_given_warnings_in_a_sync_upload_when_applied_then_the_server_recomputes_them(client, token_for, stock):
    s = stock
    from tests.integration._f6 import sync_op

    rid = uuid.uuid4()
    fields = {"type": "phyto", "performed_on": TODAY.isoformat(), "parcel_ids": [str(s["a1"])], "product_id": str(s["product"]),
              "dose": 5, "dose_unit": "L/ha", "warnings": []}
    r = client.post("/v1/sync/upload", headers=auth(token_for(s["owner"])), json={"ops": [sync_op("operations", s["farm_a"], rid, fields)]})
    assert r.status_code == 200, r.text
    stored = json.loads(sql("SELECT warnings::text FROM operation_parcels WHERE operation_id=$1", rid)[0][0])
    assert "dose_above_max" in codes(stored)


def test_given_a_treatment_recorded_despite_warnings_when_reading_the_registry_then_the_warnings_are_on_its_line(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=5, dose_unit="L/ha"))
    entry = sql("SELECT warnings::text, dose, dar_days, max_dose, catalog_version_id FROM registry_entries WHERE operation_id=$1", uuid.UUID(r.json()["id"]))
    assert len(entry) == 1 and "dose_above_max" in entry[0][0]
    assert entry[0]["dar_days"] == 7 and entry[0]["catalog_version_id"] == s["version"]
    listed = client.get(f"/v1/farms/{s['farm_a']}/registry", headers=auth(token_for(s["owner"]))).json()["items"]
    assert any("dose_above_max" in codes(i["warnings"]) for i in listed)


def test_given_a_correction_of_the_dose_when_recomputing_then_old_entries_stay_and_the_new_one_carries_the_new_warnings(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], s["product"], dose=5, dose_unit="L/ha"))
    oid = uuid.UUID(r.json()["id"])
    fixed = client.patch(f"/v1/farms/{s['farm_a']}/operations/{oid}", headers=auth(token_for(s["owner"])), json={"dose": 1})
    assert fixed.status_code == 200, fixed.text
    kinds = [(row["entry_kind"], "dose_above_max" in row["warnings"]) for row in
             sql("SELECT entry_kind, warnings::text FROM registry_entries WHERE operation_id=$1 ORDER BY recorded_at, id", oid)]
    assert kinds == [("application", True), ("reversal", True), ("application", False)]
    assert parcel_codes(fixed.json(), s["a1"]) == []


def test_given_the_check_route_when_called_then_it_returns_the_warnings_and_writes_nothing(client, token_for, stock):
    s = stock
    before = sql("SELECT count(*) FROM operations")[0][0], sql("SELECT count(*) FROM registry_entries")[0][0]
    r = client.post(f"/v1/farms/{s['farm_a']}/operations/check", headers=auth(token_for(s["owner"])),
                    json=phyto([s["a1"], s["a2"]], s["product"], dose=5, dose_unit="L/ha"))
    assert r.status_code == 200, r.text
    got = {(w.get("parcel_id"), w["code"]) for w in r.json()["warnings"]}
    assert (str(s["a1"]), "dose_above_max") in got and (str(s["a2"]), "not_authorized_for_crop") in got
    assert (sql("SELECT count(*) FROM operations")[0][0], sql("SELECT count(*) FROM registry_entries")[0][0]) == before


def test_given_a_worker_when_recording_a_treatment_then_the_warnings_are_computed_the_same_way(client, token_for, stock):
    s = stock
    r = post(client, token_for, s["worker"], s["farm_a"], phyto([s["a1"]], s["product"], dose=5, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending_validation" and parcel_codes(r.json(), s["a1"]) == ["dose_above_max"]


def test_given_a_product_of_the_catalogue_that_does_not_exist_when_recording_then_422_and_nothing_is_written(client, token_for, stock):
    s = stock
    before = sql("SELECT count(*) FROM operations")[0][0]
    r = post(client, token_for, s["owner"], s["farm_a"], phyto([s["a1"]], uuid.uuid4(), dose=1, dose_unit="L/ha"))
    assert r.status_code == 422
    assert sql("SELECT count(*) FROM operations")[0][0] == before

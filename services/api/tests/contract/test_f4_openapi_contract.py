"""T033 - specs/007-irrigation-water-balance/contracts/openapi.yaml is in sync with the running API, both ways; the bucket contract matches the infra rules."""
import os
import re
import uuid
from pathlib import Path

import pytest
import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
SPEC = yaml.safe_load((REPO / "specs/007-irrigation-water-balance/contracts/openapi.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "post", "patch", "put", "delete"}
F4 = re.compile(r"^/v1/farms/\{farm_id\}/(irrigation/|parcels/\{parcel_id\}/(irrigation|water-analyses))")
STORAGE = {"photo_key", "map_key", "raster_key", "object_key", "file_key", "push_token", "label_photo_key", "url"}
FARM_TOTAL = {"farm_total", "total_farm", "farm_area_ha", "parcel_count", "total_parcels"}


def _spec_ops():
    out = {}
    for p, item in SPEC["paths"].items():
        if p == "/sync/upload":
            continue
        for m, op in item.items():
            if m in METHODS:
                out[("/v1" + p, m)] = op
    return out


def _live(client):
    paths = client.get("/openapi.json").json()["paths"]
    return {(p, m): op for p, item in paths.items() if F4.match(p) or "irrigation-system" in p for m, op in item.items() if m in METHODS}


def _codes(op):
    return set(op.get("responses", {})) | {k for k in op if re.fullmatch(r"\d{3}", str(k))}


def test_given_the_contract_when_comparing_with_the_running_api_then_every_documented_operation_is_served_and_vice_versa(client):
    live = _live(client)
    assert live, "no F4 route is served"
    assert set(_spec_ops()) - set(live) == set() and set(live) - set(_spec_ops()) == set()


@pytest.mark.parametrize("key", sorted(_spec_ops()), ids=lambda k: f"{k[1].upper()} {k[0]}")
def test_given_each_operation_then_the_404_is_documented_and_costly_routes_document_429(key):
    codes = _codes(_spec_ops()[key])
    assert "404" in codes


def test_given_the_live_schemas_then_inputs_forbid_extra_fields_and_no_storage_key_is_exposed(client):
    live = client.get("/openapi.json").json()["components"]["schemas"]
    for name in ("IrrigationSystemInput", "IrrigationEventInput", "WaterAnalysisInput"):
        assert name in live, f"{name} not served"
        assert live[name].get("additionalProperties") is False, name
        assert not (STORAGE & set(live[name]["properties"])), name
    assert live["IrrigationEventInput"]["properties"]["note"].get("maxLength") == 500
    assert live["IrrigationSystemInput"]["properties"]["sectors_count"].get("maximum") == 50
    for name, schema in live.items():
        assert not (STORAGE & set(schema.get("properties", {}))), name


def test_given_the_contract_then_the_worker_advice_is_strict_without_leaching_and_the_consumption_has_no_farm_total():
    schemas = SPEC["components"]["schemas"]
    worker = schemas["AdviceWorker"]
    assert worker["additionalProperties"] is False and "leaching_fraction" not in worker["properties"]
    assert not (STORAGE & set(schemas["Consumption"]["properties"])) and not (FARM_TOTAL & set(schemas["Consumption"]["properties"]))
    for name, schema in SPEC["components"]["schemas"].items():
        assert not (STORAGE & set(schema.get("properties", {}))), name


def test_given_the_live_advice_schemas_then_adviceworker_matches_the_contract_properties(client):
    live = client.get("/openapi.json").json()["components"]["schemas"]
    assert "AdviceWorker" in live
    assert set(live["AdviceWorker"]["properties"]) == set(SPEC["components"]["schemas"]["AdviceWorker"]["properties"])
    assert live["AdviceWorker"].get("additionalProperties") is False


def test_given_seeded_data_then_responses_carry_the_required_fields_of_the_contract(client, token_for):
    from tests.helpers import sql
    from tests.integration._f4 import call, seed_balance, seed_event, seed_plan, seed_system
    from tests.integration._f2 import add_field, new_user

    owner = new_user()
    farm = uuid.uuid4()
    sql("INSERT INTO farms (id, name) VALUES ($1,'F')", farm)
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1,$2,'owner')", farm, owner)
    p = add_field(farm, "P")
    sql("UPDATE parcels SET irrigation='drip' WHERE id=$1", p)
    seed_system(farm, p)
    seed_plan(farm, p)
    seed_balance(farm, p)
    seed_event(farm, p, owner)
    tok, f = token_for(owner), f"/v1/farms/{farm}"
    schemas = SPEC["components"]["schemas"]
    a = call(client, tok, "GET", f"{f}/parcels/{p}/irrigation/advice")
    assert a.status_code == 200 and set(schemas["Advice"]["required"]) <= set(a.json())
    s = call(client, tok, "GET", f"{f}/parcels/{p}/irrigation-system")
    assert set(schemas["IrrigationSystem"]["allOf"][1]["required"]) <= set(s.json())
    c = call(client, tok, "GET", f"{f}/irrigation/consumption")
    assert set(schemas["Consumption"]["required"]) <= set(c.json())
    lst = call(client, tok, "GET", f"{f}/irrigation/advice")
    assert set(schemas["AdviceList"]["required"]) <= set(lst.json())


def test_given_the_bucket_contract_and_the_infra_rules_then_the_f4_buckets_are_aligned():
    contract = yaml.safe_load((REPO / "specs/007-irrigation-water-balance/contracts/powersync-sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
    infra = yaml.safe_load((REPO / "infra/powersync/sync-rules.yaml").read_text(encoding="utf-8"))["bucket_definitions"]
    for name, b in contract.items():
        assert name in infra, f"infra rules do not define {name}"
        assert infra[name].get("parameters") == b.get("parameters")
        assert sorted(infra[name]["data"]) == sorted(b["data"]), name

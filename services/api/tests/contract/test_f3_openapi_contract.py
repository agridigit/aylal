"""T028 - specs/006-dashboard-monitoring/contracts/openapi.yaml is in sync with the running API, both ways."""
import os
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
SPEC = yaml.safe_load((REPO / "specs/006-dashboard-monitoring/contracts/openapi.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "post", "patch", "put", "delete"}
F3 = re.compile(r"^/v1/farms/\{farm_id\}/(dashboard|weather|alerts|zones|summary|parcels/\{parcel_id\}/(status|vigor))")
STAFF_ONLY = {"alert.dismiss", "zone.dismiss", "imagery.reprocess"}
STORAGE = {"photo_key", "map_key", "raster_key", "object_key", "push_token", "label_photo_key"}


def _norm(path):
    return "/v1" + re.sub(r"\{[a-z_]+\}", lambda m: m.group(0), path)


def _spec_ops():
    return {(_norm(p), m): op for p, item in SPEC["paths"].items() for m, op in item.items() if m in METHODS}


def _codes(op):
    """Documented status codes. The contract places some codes as siblings of `responses` (indentation defect): both count."""
    return set(op.get("responses", {})) | {k for k in op if re.fullmatch(r"\d{3}", str(k))}


def _live(client):
    paths = client.get("/openapi.json").json()["paths"]
    return {(p, m): op for p, item in paths.items() if F3.match(p) for m, op in item.items() if m in METHODS}


def test_given_the_contract_when_comparing_with_the_running_api_then_every_documented_operation_is_served(client):
    live = _live(client)
    assert live, "no F3 route is served"
    assert set(_spec_ops()) - set(live) == set()


def test_given_the_running_api_then_every_served_f3_operation_is_documented(client):
    live = _live(client)
    assert live, "no F3 route is served"
    assert set(live) - set(_spec_ops()) == set()


def test_given_the_contract_then_every_action_is_in_the_rights_matrix_and_none_is_financial():
    from app.domain.roles import MATRIX

    for op in _spec_ops().values():
        a = op["x-action"]
        assert a in MATRIX, a
        assert "finance" not in a


@pytest.mark.parametrize("key", sorted(_spec_ops()), ids=lambda k: f"{k[1].upper()} {k[0]}")
def test_given_each_operation_then_the_error_statuses_are_documented(key):
    op = _spec_ops()[key]
    codes = _codes(op)
    assert "404" in codes
    if op["x-action"] in STAFF_ONLY:
        assert "403" in codes
    if op["x-action"] == "imagery.reprocess" or key[0].endswith("/observations/photo") or key[0].endswith("/vigor"):
        assert "429" in codes


def test_given_the_live_schemas_then_inputs_forbid_extra_fields_and_no_storage_key_is_exposed(client):
    live = client.get("/openapi.json").json()["components"]["schemas"]
    assert "ObservationInput" in live, "F3 input schema not served"
    assert live["ObservationInput"].get("additionalProperties") is False
    assert "photo_key" not in live["ObservationInput"]["properties"] and live["ObservationInput"]["properties"]["note"].get("maxLength") == 500
    for name, schema in live.items():
        assert not (STORAGE & set(schema.get("properties", {}))), name


def test_given_the_contract_schemas_then_none_carries_a_storage_key():
    for name, schema in SPEC["components"]["schemas"].items():
        assert not (STORAGE & set(schema.get("properties", {}))), name


def test_given_seeded_data_then_responses_carry_the_required_fields_of_the_contract(client, token_for):
    from tests.helpers import sql
    from tests.integration._f2 import add_field, new_user
    from tests.integration._f3 import seed_alert, seed_scene, seed_status, seed_zone

    owner = new_user()
    farm = __import__("uuid").uuid4()
    sql("INSERT INTO farms (id, name) VALUES ($1,'F')", farm)
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1,$2,'owner')", farm, owner)
    p = add_field(farm, "P")
    seed_status(farm, p, "red")
    seed_alert(farm, p)
    seed_zone(farm, p)
    seed_scene(farm, p)
    h = {"Authorization": f"Bearer {token_for(owner)}"}
    schemas = SPEC["components"]["schemas"]
    f = f"/v1/farms/{farm}"
    d = client.get(f"{f}/dashboard", headers=h)
    assert d.status_code == 200, d.text
    assert set(schemas["Dashboard"]["required"]) <= set(d.json())
    assert set(schemas["ParcelStatus"]["required"]) <= set(d.json()["parcels"][0])
    assert set(schemas["Counts"]["required"]) <= set(d.json()["counts"])
    a = client.get(f"{f}/alerts", headers=h).json()
    assert set(schemas["Alert"]["required"]) <= set(a[0])
    z = client.get(f"{f}/zones", headers=h).json()
    assert set(schemas["Zone"]["required"]) <= set(z[0])
    v = client.get(f"{f}/parcels/{p}/vigor", headers=h).json()
    assert set(schemas["VigorSeries"]["required"]) <= set(v) and set(schemas["VigorPoint"]["required"]) <= set(v["points"][0])
    assert all(80 <= pt["clear_pct"] <= 100 for pt in v["points"])
    w = client.get(f"{f}/weather", headers=h).json()
    assert set(schemas["Freshness"]["required"]) <= set(w)

"""T048 - /v1/farms, /v1/me*, /v1/geo/* conform to contracts/openapi.yaml."""
import os
from pathlib import Path

import yaml

from tests.helpers import auth
from tests.integration._auth_flow import _test_otp, login  # noqa: F401

SPEC = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "specs/002-account-onboarding-farm/contracts/openapi.yaml"
PATHS = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["paths"]
ROUTES = ["/v1/me", "/v1/me/consents", "/v1/me/consents/{purpose}", "/v1/farms", "/v1/farms/{farm_id}",
          "/v1/geo/regions", "/v1/geo/communes", "/v1/geo/locate"]
CASA = {"lat": 33.5731, "lon": -7.5898}


def test_given_the_contract_when_comparing_with_the_running_api_then_every_route_and_method_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path in ROUTES:
        assert path in PATHS and path in live, path
        assert set(PATHS[path]) <= set(live[path]), (path, set(PATHS[path]) - set(live[path]))


def test_given_a_farm_creation_then_it_returns_the_documented_201_and_422(client):
    s = login(client)
    h = auth(s["access_token"])
    assert "201" in PATHS["/v1/farms"]["post"]["responses"]
    r = client.post("/v1/farms", json={"name": "F", "location": CASA}, headers=h)
    assert r.status_code == 201 and {"id", "name", "owner_id", "commune_id", "area_ha", "role"} <= set(r.json())
    assert client.post("/v1/farms", json={"name": "F"}, headers=h).status_code == 422
    assert client.get(f"/v1/farms/{r.json()['id']}", headers=h).status_code == 200


def test_given_me_when_patching_and_consenting_then_documented_statuses_are_returned(client):
    s = login(client)
    h = auth(s["access_token"])
    assert client.patch("/v1/me", json={"language": "ary"}, headers=h).status_code == 200
    assert client.post("/v1/me/consents", json={"purpose": "data_policy", "text_version": "2026-01"}, headers=h).status_code == 201
    assert client.get("/v1/me/consents", headers=h).status_code == 200
    assert client.delete("/v1/me/consents/data_policy", headers=h).status_code == 204


def test_given_geo_routes_then_the_documented_statuses_are_returned(client):
    h = auth(login(client)["access_token"])
    assert client.get("/v1/geo/regions", headers=h).status_code == 200
    assert client.get("/v1/geo/communes", headers=h).status_code == 200
    assert client.get("/v1/geo/locate", params=CASA, headers=h).status_code == 200
    assert client.get("/v1/geo/locate", params={"lat": 48.85, "lon": 2.35}, headers=h).status_code == 404

"""T066 - invitations, members, deletion and export conform to contracts/openapi.yaml."""
import os
from pathlib import Path

import yaml

from tests.helpers import auth
from tests.integration._auth_flow import _test_otp, login  # noqa: F401

SPEC = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "specs/002-account-onboarding-farm/contracts/openapi.yaml"
PATHS = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["paths"]
ROUTES = ["/v1/farms/{farm_id}/members", "/v1/farms/{farm_id}/members/{user_id}",
          "/v1/farms/{farm_id}/members/{user_id}/parcels", "/v1/farms/{farm_id}/invitations",
          "/v1/farms/{farm_id}/invitations/{invitation_id}", "/v1/me/deletion", "/v1/me/export",
          "/v1/me/deletion/impact"]
CASA = {"lat": 33.5731, "lon": -7.5898}


def test_given_the_contract_when_comparing_with_the_running_api_then_every_team_and_account_route_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path in ROUTES:
        assert path in PATHS and path in live, path
        assert set(PATHS[path]) <= set(live[path]), (path, set(PATHS[path]) - set(live[path]))


def test_given_an_invitation_then_the_documented_status_codes_are_returned(client):
    owner = login(client)
    h = auth(owner["access_token"])
    farm = client.post("/v1/farms", json={"name": "F", "location": CASA}, headers=h).json()["id"]
    codes = PATHS["/v1/farms/{farm_id}/invitations"]["post"]["responses"]
    assert {"201", "409", "422"} <= set(codes)
    r = client.post(f"/v1/farms/{farm}/invitations", json={"phone": "+212699887766", "role": "worker"}, headers=h)
    assert r.status_code == 201 and {"id", "phone", "role", "status", "expires_at"} <= set(r.json())
    assert client.post(f"/v1/farms/{farm}/invitations", json={"phone": "bad", "role": "worker"}, headers=h).status_code == 422
    listed = client.get(f"/v1/farms/{farm}/invitations", headers=h)
    assert listed.status_code == 200 and listed.json()[0]["id"] == r.json()["id"]
    assert client.delete(f"/v1/farms/{farm}/invitations/{r.json()['id']}", headers=h).status_code == 204


def test_given_a_deletion_request_then_the_documented_202_is_returned(client):
    s = login(client)
    assert "202" in PATHS["/v1/me/deletion"]["post"]["responses"]
    r = client.post("/v1/me/deletion", json={"confirm": True}, headers=auth(s["access_token"]))
    assert r.status_code == 202 and {"deletion_requested_at", "deletion_deadline"} <= set(r.json())

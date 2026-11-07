"""T024 - /v1/auth/* conforms to specs/002-account-onboarding-farm/contracts (openapi.yaml, auth-otp.md)."""
import os
from pathlib import Path

import yaml

from tests.integration._auth_flow import CODE, PHONE, _test_otp  # noqa: F401

SPEC = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "specs/002-account-onboarding-farm/contracts/openapi.yaml"
PATHS = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["paths"]


def test_given_the_contract_when_comparing_with_the_running_api_then_every_auth_route_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path in ("/v1/auth/otp/request", "/v1/auth/otp/verify", "/v1/auth/refresh", "/v1/auth/logout"):
        assert path in PATHS and path in live, path


def test_given_the_verify_response_then_it_has_the_contract_fields(client):
    client.post("/v1/auth/otp/request", json={"phone": PHONE})
    r = client.post("/v1/auth/otp/verify", json={"phone": PHONE, "code": CODE})
    assert r.status_code == 200 and "200" in PATHS["/v1/auth/otp/verify"]["post"]["responses"]
    body = r.json()
    assert {"access_token", "refresh_token", "user", "farms"} <= set(body)
    assert {"id", "phone", "status"} <= set(body["user"])


def test_given_each_documented_error_status_then_the_api_returns_the_documented_body(client):
    assert client.post("/v1/auth/otp/request", json={"phone": "12"}).status_code == 422
    client.post("/v1/auth/otp/request", json={"phone": PHONE})
    again = client.post("/v1/auth/otp/request", json={"phone": PHONE})
    assert again.status_code == 429
    assert again.json()["detail"]["code"] == "otp_rate_limited" and again.json()["detail"]["retry_after"] > 0
    bad = client.post("/v1/auth/otp/verify", json={"phone": PHONE, "code": "111111"})
    assert bad.status_code == 400 and set(bad.json()["detail"]) == {"code", "attempts_left"}
    assert client.post("/v1/auth/refresh", json={"refresh_token": "x"}).status_code == 401


def test_given_the_logout_contract_then_a_valid_call_answers_204(client):
    client.post("/v1/auth/otp/request", json={"phone": PHONE})
    s = client.post("/v1/auth/otp/verify", json={"phone": PHONE, "code": CODE}).json()
    r = client.post(
        "/v1/auth/logout", json={"refresh_token": s["refresh_token"]},
        headers={"Authorization": f"Bearer {s['access_token']}"},
    )
    assert r.status_code == 204 and "204" in PATHS["/v1/auth/logout"]["post"]["responses"]

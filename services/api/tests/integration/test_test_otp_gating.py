"""T005 - the fixed test OTP exists only in dev/test with AYLAL_ENABLE_TEST_OTP=1."""
import pytest
from fastapi.testclient import TestClient

STRONG = "s" * 40
PHONE = "+212612345678"


def _set(monkeypatch, env, flag):
    monkeypatch.setenv("AYLAL_JWT_SECRET", STRONG)
    monkeypatch.setenv("AYLAL_OTP_PEPPER", "p" * 40)
    for k, v in (("AYLAL_ENV", env), ("AYLAL_ENABLE_TEST_OTP", flag)):
        monkeypatch.delenv(k, raising=False) if v is None else monkeypatch.setenv(k, v)


def test_given_prod_with_test_otp_flag_when_the_app_starts_then_it_refuses_to_start(client, monkeypatch):
    _set(monkeypatch, "prod", "1")
    with pytest.raises(Exception):
        with TestClient(client.app):
            pass


def test_given_prod_with_test_otp_flag_when_requesting_a_code_then_no_request_is_served(client, monkeypatch):
    _set(monkeypatch, "prod", "1")
    with pytest.raises(Exception):
        client.post("/v1/auth/otp/request", json={"phone": PHONE})


def test_given_test_env_without_flag_when_verifying_the_test_code_then_it_is_refused(client, monkeypatch):
    _set(monkeypatch, "test", None)
    assert client.post("/v1/auth/otp/request", json={"phone": PHONE}).status_code == 202
    r = client.post("/v1/auth/otp/verify", json={"phone": PHONE, "code": "000000"})
    assert r.status_code == 400


def test_given_test_env_with_flag_when_verifying_the_test_code_then_a_session_is_issued(client, monkeypatch):
    _set(monkeypatch, "test", "1")
    assert client.post("/v1/auth/otp/request", json={"phone": PHONE}).status_code == 202
    r = client.post("/v1/auth/otp/verify", json={"phone": PHONE, "code": "000000"})
    assert r.status_code == 200 and "access_token" in r.json()

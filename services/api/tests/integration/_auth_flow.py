"""Shared helpers for the F1 auth integration tests (test OTP mode, fixed code 000000)."""
import pytest

PHONE = "+212612345678"
CODE = "000000"


@pytest.fixture(autouse=True)
def _test_otp(monkeypatch):
    monkeypatch.setenv("AYLAL_JWT_SECRET", "s" * 40)
    monkeypatch.setenv("AYLAL_OTP_PEPPER", "p" * 40)
    monkeypatch.setenv("AYLAL_ENV", "test")
    monkeypatch.setenv("AYLAL_ENABLE_TEST_OTP", "1")


def login(client, phone=PHONE):
    assert client.post("/v1/auth/otp/request", json={"phone": phone}).status_code == 202
    r = client.post("/v1/auth/otp/verify", json={"phone": phone, "code": CODE})
    assert r.status_code == 200, r.text
    return r.json()

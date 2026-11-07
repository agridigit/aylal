"""T079 client IP behind a proxy, T080 hourly cap and resend delay under concurrency."""
import asyncio

import httpx
import pytest

from tests.helpers import sql

PROXY = "10.0.0.5"
PHONES = ["+212612345678", "+212612345679", "+212612345680"]


@pytest.fixture(autouse=True)
def _env(monkeypatch, clean_db):
    monkeypatch.setenv("AYLAL_JWT_SECRET", "s" * 40)
    monkeypatch.setenv("AYLAL_OTP_PEPPER", "p" * 40)
    monkeypatch.setenv("AYLAL_ENV", "test")
    monkeypatch.setenv("AYLAL_ENABLE_TEST_OTP", "1")
    monkeypatch.delenv("AYLAL_TRUSTED_PROXIES", raising=False)


def _post(phone, headers=None, peer=PROXY):
    async def _run():
        from app.main import app

        transport = httpx.ASGITransport(app=app, client=(peer, 4242))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.post("/v1/auth/otp/request", json={"phone": phone}, headers=headers or {})

    return asyncio.run(_run())


def _ip(phone):
    return sql("SELECT client_ip FROM otp_challenges WHERE phone_e164=$1", phone)[0][0]


def test_given_no_trusted_proxy_configured_when_requesting_then_forwarded_headers_are_ignored():
    assert _post(PHONES[0], {"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.9"}).status_code == 202
    assert _ip(PHONES[0]) == PROXY


def test_given_request_from_trusted_proxy_when_requesting_then_the_forwarded_ip_is_used(monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", PROXY)
    assert _post(PHONES[0], {"X-Real-IP": "203.0.113.9"}).status_code == 202
    assert _ip(PHONES[0]) == "203.0.113.9"


def test_given_request_from_untrusted_peer_when_requesting_then_forwarded_headers_are_ignored(monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", PROXY)
    assert _post(PHONES[0], {"X-Forwarded-For": "203.0.113.9"}, peer="198.51.100.7").status_code == 202
    assert _ip(PHONES[0]) == "198.51.100.7"


def test_given_two_clients_behind_the_same_proxy_when_one_hits_the_ip_cap_then_the_other_is_not_limited(monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", PROXY)
    import app.routers.auth as auth

    monkeypatch.setattr(auth, "MAX_SENDS_PER_IP", 1)
    assert _post(PHONES[0], {"X-Real-IP": "203.0.113.1"}).status_code == 202
    assert _post(PHONES[1], {"X-Real-IP": "203.0.113.1"}).status_code == 429
    assert _post(PHONES[2], {"X-Real-IP": "203.0.113.2"}).status_code == 202


@pytest.mark.parametrize("headers", [{}, {"X-Real-IP": "not-an-ip"}])
def test_given_unknown_client_ip_when_requesting_then_no_shared_ip_bucket_is_used(monkeypatch, headers):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", PROXY)
    import app.routers.auth as auth

    monkeypatch.setattr(auth, "MAX_SENDS_PER_IP", 1)
    assert _post(PHONES[0], headers).status_code == 202
    assert _post(PHONES[1], headers).status_code == 202  # limited by phone alone
    assert _ip(PHONES[0]) is None


async def _burst(phone, n):
    from app.main import app

    transport = httpx.ASGITransport(app=app, client=("198.51.100.7", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        return await asyncio.gather(*[c.post("/v1/auth/otp/request", json={"phone": phone}) for _ in range(n)])


def test_given_parallel_requests_for_a_new_phone_when_requesting_then_the_resend_delay_is_not_bypassed():
    responses = asyncio.run(_burst(PHONES[0], 10))
    assert sum(r.status_code == 202 for r in responses) == 1
    assert all(r.status_code in (202, 429) for r in responses)
    assert sql("SELECT count(*) FROM otp_challenges WHERE phone_e164=$1", PHONES[0])[0][0] == 1


def test_given_four_sends_in_the_hour_when_requesting_in_parallel_then_the_cap_of_five_is_never_exceeded():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    for _ in range(4):
        assert c.post("/v1/auth/otp/request", json={"phone": PHONES[0]}).status_code in (202, 429)
        sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - interval '10 minutes'")
    before = sql("SELECT count(*) FROM otp_challenges WHERE phone_e164=$1", PHONES[0])[0][0]
    responses = asyncio.run(_burst(PHONES[0], 10))
    after = sql("SELECT count(*) FROM otp_challenges WHERE phone_e164=$1", PHONES[0])[0][0]
    assert after <= 5
    assert after - before == sum(r.status_code == 202 for r in responses) <= 1

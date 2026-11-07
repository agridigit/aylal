"""T076 - atomic failure counter and single consumption under concurrency (decisions.md, finding 2)."""
import asyncio

import httpx
import pytest

from tests.helpers import sql

PHONE = "+212612345678"
PARALLEL = 20


@pytest.fixture(autouse=True)
def _test_otp(monkeypatch, clean_db):
    monkeypatch.setenv("AYLAL_JWT_SECRET", "s" * 40)
    monkeypatch.setenv("AYLAL_OTP_PEPPER", "p" * 40)
    monkeypatch.setenv("AYLAL_ENV", "test")
    monkeypatch.setenv("AYLAL_ENABLE_TEST_OTP", "1")


async def _burst(code: str) -> list[httpx.Response]:
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        return await asyncio.gather(
            *[c.post("/v1/auth/otp/verify", json={"phone": PHONE, "code": code}) for _ in range(PARALLEL)]
        )


def _seed_challenge():
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).post("/v1/auth/otp/request", json={"phone": PHONE}).status_code == 202


def test_given_parallel_wrong_codes_when_verifying_then_failures_never_exceed_three():
    _seed_challenge()
    responses = asyncio.run(_burst("111111"))
    failed = sql("SELECT failed_attempts FROM otp_challenges WHERE phone_e164=$1", PHONE)[0][0]
    assert failed == 3
    assert sum(r.status_code == 400 for r in responses) <= 2
    assert all(r.status_code in (400, 423) for r in responses)


def test_given_parallel_right_codes_when_verifying_then_the_challenge_is_consumed_once():
    _seed_challenge()
    responses = asyncio.run(_burst("000000"))
    assert sorted({r.status_code for r in responses} - {200}) <= [400]
    assert sum(r.status_code == 200 for r in responses) == 1
    assert sql("SELECT count(*) FROM refresh_tokens")[0][0] == 1
    assert sql("SELECT count(*) FROM users WHERE phone_e164=$1", PHONE)[0][0] == 1

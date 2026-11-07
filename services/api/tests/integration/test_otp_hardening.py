"""T075 - OTP lock per phone over a window, resend limits (decisions.md, finding 1)."""
import pytest

from tests.helpers import sql

PHONE = "+212612345678"
WRONG, RIGHT = "111111", "000000"


@pytest.fixture(autouse=True)
def _test_otp(monkeypatch):
    monkeypatch.setenv("AYLAL_JWT_SECRET", "s" * 40)
    monkeypatch.setenv("AYLAL_OTP_PEPPER", "p" * 40)
    monkeypatch.setenv("AYLAL_ENV", "test")
    monkeypatch.setenv("AYLAL_ENABLE_TEST_OTP", "1")


def _request(client, phone=PHONE):
    return client.post("/v1/auth/otp/request", json={"phone": phone})


def _verify(client, code, phone=PHONE):
    return client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})


def _age_sends(minutes=10):
    """Move every send into the past: only the hourly window still counts them."""
    sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - make_interval(mins => $1)", minutes)


def test_given_two_failures_when_requesting_a_new_code_then_the_third_failure_locks_the_phone(client):
    assert _request(client).status_code == 202
    assert _verify(client, WRONG).status_code == 400
    assert _verify(client, WRONG).status_code == 400
    _age_sends()
    assert _request(client).status_code == 202
    assert _verify(client, WRONG).status_code == 423


def test_given_a_locked_phone_when_requesting_a_new_code_then_the_right_code_is_still_refused(client):
    assert _request(client).status_code == 202
    for _ in range(3):
        _verify(client, WRONG)
    _age_sends()
    _request(client)
    r = _verify(client, RIGHT)
    assert r.status_code == 423
    assert r.json()["detail"]["code"] == "otp_locked"


def test_given_a_new_code_when_requested_then_only_one_challenge_stays_active(client):
    assert _request(client).status_code == 202
    _age_sends()
    assert _request(client).status_code == 202
    active = sql(
        "SELECT count(*) FROM otp_challenges WHERE phone_e164=$1 AND consumed_at IS NULL AND expires_at > now()",
        PHONE,
    )[0][0]
    assert active == 1


def test_given_a_code_just_sent_when_requesting_again_immediately_then_429_with_retry_after(client):
    assert _request(client).status_code == 202
    r = _request(client)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_given_many_sends_to_one_phone_within_an_hour_when_requesting_then_429_before_ten_sends(client):
    codes = []
    for _ in range(10):
        codes.append(_request(client).status_code)
        _age_sends(minutes=2)  # past the resend delay, inside the hourly window
    assert 429 in codes
    assert codes[0] == 202


def test_given_many_sends_from_one_ip_to_distinct_phones_when_requesting_then_429_before_sixty_sends(client):
    codes = [_request(client, f"+2126{n:08d}").status_code for n in range(10_000_000, 10_000_060)]
    assert codes[0] == 202
    assert 429 in codes

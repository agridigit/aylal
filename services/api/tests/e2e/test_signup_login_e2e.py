"""T025 - full signup, then an existing user comes back (R1-A1, R1-A3). Stack needs AYLAL_ENV=test + AYLAL_ENABLE_TEST_OTP=1."""
import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
PHONE = "+212677001122"
CODE = "000000"


def _login(c: httpx.Client) -> dict:
    assert c.post("/auth/otp/request", json={"phone": PHONE}).status_code == 202
    r = c.post("/auth/otp/verify", json={"phone": PHONE, "code": CODE})
    assert r.status_code == 200, r.text
    return r.json()


def test_given_a_new_user_when_signing_up_then_the_account_exists_and_the_session_works() -> None:
    sql("DELETE FROM otp_challenges WHERE phone_e164=$1", PHONE)
    sql("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM users WHERE phone_e164=$1", PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        s = _login(c)
        assert s["farms"] == []
        refreshed = c.post("/auth/refresh", json={"refresh_token": s["refresh_token"]})
        assert refreshed.status_code == 200
    assert len(sql("SELECT 1 FROM users WHERE phone_e164=$1", PHONE)) == 1


def test_given_an_existing_user_when_logging_in_again_then_the_same_account_is_found() -> None:
    sql("DELETE FROM otp_challenges WHERE phone_e164=$1", PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        first = _login(c)
        sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - interval '2 minutes' WHERE phone_e164=$1", PHONE)
        second = _login(c)
        out = c.post(
            "/auth/logout", json={"refresh_token": second["refresh_token"]},
            headers={"Authorization": f"Bearer {second['access_token']}"},
        )
    assert second["user"]["id"] == first["user"]["id"]
    assert out.status_code == 204
    assert len(sql("SELECT 1 FROM users WHERE phone_e164=$1", PHONE)) == 1

"""T042 - language, consent, profile on the running stack (R2-A3, R3-A2, R3-A3)."""
import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
PHONE = "+212677003344"


def _fresh() -> None:
    sql("DELETE FROM otp_challenges WHERE phone_e164=$1", PHONE)
    sql("DELETE FROM farm_members WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM consents WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM users WHERE phone_e164=$1", PHONE)


def test_given_a_new_user_when_choosing_language_consenting_and_naming_then_the_profile_is_complete() -> None:
    _fresh()
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        assert c.post("/auth/otp/request", json={"phone": PHONE}).status_code == 202
        s = c.post("/auth/otp/verify", json={"phone": PHONE, "code": "000000"}).json()
        h = {"Authorization": f"Bearer {s['access_token']}"}
        assert c.patch("/me", json={"language": "ary"}, headers=h).status_code == 200
        assert c.patch("/me", json={"display_name": "Hassan"}, headers=h).status_code == 403
        assert c.post("/me/consents", json={"purpose": "data_policy", "text_version": "2026-01"}, headers=h).status_code == 201
        me = c.patch("/me", json={"display_name": "Hassan"}, headers=h).json()
        assert (me["language"], me["display_name"], me["status"]) == ("ary", "Hassan", "active")

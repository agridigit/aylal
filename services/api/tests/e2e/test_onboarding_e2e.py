"""T050 - complete service journey: language, number, code, consent, nickname, farm (R4-A1, R4-A4)."""
import time

import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
PHONE = "+212677005566"
BUDGET_SECONDS = 120


def test_given_a_new_user_when_running_the_whole_journey_then_the_farm_exists_within_the_budget() -> None:
    sql("DELETE FROM otp_challenges WHERE phone_e164=$1", PHONE)
    sql("DELETE FROM farm_members WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM consents WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM farms WHERE owner_id IN (SELECT id FROM users WHERE phone_e164=$1)", PHONE)
    sql("DELETE FROM users WHERE phone_e164=$1", PHONE)
    started = time.monotonic()
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        c.post("/auth/otp/request", json={"phone": PHONE})
        s = c.post("/auth/otp/verify", json={"phone": PHONE, "code": "000000"}).json()
        h = {"Authorization": f"Bearer {s['access_token']}"}
        c.patch("/me", json={"language": "fr"}, headers=h)
        c.post("/me/consents", json={"purpose": "data_policy", "text_version": "2026-01"}, headers=h)
        assert c.patch("/me", json={"display_name": "Hassan"}, headers=h).status_code == 200
        r = c.post("/farms", json={"name": "Ferme", "location": {"lat": 33.5731, "lon": -7.5898}}, headers=h)
        assert r.status_code == 201 and r.json()["role"] == "owner" and r.json()["commune_id"]
        assert [f["id"] for f in c.get("/farms", headers=h).json()] == [r.json()["id"]]
    assert time.monotonic() - started < BUDGET_SECONDS

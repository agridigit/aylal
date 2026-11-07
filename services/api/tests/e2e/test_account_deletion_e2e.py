"""T056 - account deletion and export on the running stack (R8-A1, R8-A2, R8-A3)."""
import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
OWNER, WORKER = "+212677004455", "+212677004456"
CASA = {"lat": 33.5731, "lon": -7.5898}


def _fresh() -> None:
    for p in (OWNER, WORKER):
        sql("DELETE FROM otp_challenges WHERE phone_e164=$1", p)
        sql("DELETE FROM farm_members WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", p)
    sql("DELETE FROM farms WHERE owner_id IN (SELECT id FROM users WHERE phone_e164=$1)", OWNER)
    for p in (OWNER, WORKER):
        sql("DELETE FROM consents WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", p)
        sql("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", p)
        sql("DELETE FROM users WHERE phone_e164=$1", p)


def _login(c, phone):
    assert c.post("/auth/otp/request", json={"phone": phone}).status_code == 202
    return c.post("/auth/otp/verify", json={"phone": phone, "code": "000000"}).json()


def test_given_an_owner_with_members_when_requesting_deletion_then_warned_signed_out_and_given_the_deadline() -> None:
    _fresh()
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        owner, worker = _login(c, OWNER), _login(c, WORKER)
        h = {"Authorization": f"Bearer {owner['access_token']}"}
        farm = c.post("/farms", json={"name": "Atlas", "location": CASA}, headers=h).json()["id"]
        sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1::uuid, $2::uuid, 'worker')", farm, worker["user"]["id"])
        impact = c.get("/me/deletion/impact", headers=h).json()
        assert impact["owned_farms"] == [{"farm_id": farm, "name": "Atlas", "other_members": 1}]
        assert c.post("/me/export", headers=h).status_code == 202
        r = c.post("/me/deletion", json={"confirm": True}, headers=h)
        assert r.status_code == 202 and r.json()["deletion_deadline"]
        assert c.post("/auth/refresh", json={"refresh_token": owner["refresh_token"]}).status_code == 401
        assert c.get("/me", headers=h).status_code == 401
    _fresh()

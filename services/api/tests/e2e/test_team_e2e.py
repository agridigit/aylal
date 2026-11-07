"""T068 - invite, join, scope and remove on the running stack (R6-A1 to R6-A5)."""
import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
OWNER, MEMBER = "+212677005566", "+212677005567"
CASA = {"lat": 33.5731, "lon": -7.5898}
PHONES = (OWNER, MEMBER)


def _fresh() -> None:
    for p in PHONES:
        sql("DELETE FROM otp_challenges WHERE phone_e164=$1", p)
    sql("DELETE FROM invitations WHERE phone_e164 = ANY($1)", list(PHONES))
    for p in PHONES:
        sql("DELETE FROM farm_members WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", p)
    sql("DELETE FROM farms WHERE owner_id IN (SELECT id FROM users WHERE phone_e164=$1)", OWNER)
    for p in PHONES:
        sql("DELETE FROM consents WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", p)
        sql("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", p)
        sql("DELETE FROM users WHERE phone_e164=$1", p)


def _login(c, phone):
    assert c.post("/auth/otp/request", json={"phone": phone}).status_code == 202
    return c.post("/auth/otp/verify", json={"phone": phone, "code": "000000"}).json()


def test_given_an_invited_worker_when_signing_up_then_joined_with_the_role_then_role_changed_then_removed() -> None:
    _fresh()
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        owner = _login(c, OWNER)
        oh = {"Authorization": f"Bearer {owner['access_token']}"}
        farm = c.post("/farms", json={"name": "Atlas", "location": CASA}, headers=oh).json()["id"]
        assert c.post(f"/farms/{farm}/invitations", json={"phone": MEMBER, "role": "worker"}, headers=oh).status_code == 201
        member = _login(c, MEMBER)
        mh = {"Authorization": f"Bearer {member['access_token']}"}
        assert [(f["id"], f["role"]) for f in member["farms"]] == [(farm, "worker")]
        assert c.patch(f"/farms/{farm}", json={"name": "X"}, headers=mh).status_code == 403
        uid = member["user"]["id"]
        assert c.patch(f"/farms/{farm}/members/{uid}", json={"role": "manager"}, headers=oh).status_code == 200
        assert c.patch(f"/farms/{farm}", json={"name": "Atlas 2"}, headers=mh).status_code == 200
        assert c.delete(f"/farms/{farm}/members/{uid}", headers=oh).status_code == 204
        assert c.get(f"/farms/{farm}", headers=mh).status_code == 404
    _fresh()

"""T039 - /v1/me/consents, consent-gated profile, pending purge after 24 h (R3-A2, R3-A3, FR-012)."""
import asyncio
import datetime as dt

from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login  # noqa: F401

GRANT = {"purpose": "data_policy", "text_version": "2026-01"}


def _h(s):
    return auth(s["access_token"])


def test_given_a_verified_user_when_granting_consent_then_it_is_stored_versioned_and_timestamped(client):
    s = login(client)
    r = client.post("/v1/me/consents", json=GRANT, headers=_h(s))
    assert r.status_code == 201
    rows = sql("SELECT purpose, text_version, granted_at, withdrawn_at FROM consents WHERE user_id = $1::uuid", s["user"]["id"])
    assert len(rows) == 1 and rows[0]["text_version"] == "2026-01" and rows[0]["granted_at"] and rows[0]["withdrawn_at"] is None


def test_given_a_consent_without_version_when_posting_then_422(client):
    s = login(client)
    assert client.post("/v1/me/consents", json={"purpose": "data_policy"}, headers=_h(s)).status_code == 422


def test_given_granted_consents_when_listing_then_they_are_returned(client):
    s = login(client)
    client.post("/v1/me/consents", json=GRANT, headers=_h(s))
    r = client.get("/v1/me/consents", headers=_h(s))
    assert r.status_code == 200
    assert [(c["purpose"], c["text_version"], c["withdrawn_at"]) for c in r.json()] == [("data_policy", "2026-01", None)]


def test_given_a_consent_when_withdrawn_then_204_and_it_is_marked_withdrawn(client):
    s = login(client)
    client.post("/v1/me/consents", json=GRANT, headers=_h(s))
    assert client.delete("/v1/me/consents/data_policy", headers=_h(s)).status_code == 204
    assert client.get("/v1/me/consents", headers=_h(s)).json()[0]["withdrawn_at"] is not None


def test_given_users_when_listing_consents_then_each_sees_only_their_own(client):
    a, b = login(client), login(client, "+212611112222")
    client.post("/v1/me/consents", json=GRANT, headers=_h(a))
    assert client.get("/v1/me/consents", headers=_h(b)).json() == []


def test_given_no_session_when_using_consents_then_401(client):
    assert client.get("/v1/me/consents").status_code == 401
    assert client.post("/v1/me/consents", json=GRANT).status_code == 401


def test_given_no_consent_when_setting_a_display_name_then_403_and_no_personal_data_is_kept(client):
    s = login(client)
    r = client.patch("/v1/me", json={"display_name": "Hassan"}, headers=_h(s))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "consent_required"
    assert sql("SELECT display_name FROM users WHERE id = $1::uuid", s["user"]["id"])[0][0] is None


def test_given_consent_when_setting_a_display_name_then_the_profile_is_created_and_the_account_active(client):
    s = login(client)
    client.post("/v1/me/consents", json=GRANT, headers=_h(s))
    r = client.patch("/v1/me", json={"display_name": "Hassan"}, headers=_h(s))
    assert r.status_code == 200 and r.json()["display_name"] == "Hassan" and r.json()["status"] == "active"


def test_given_extra_personal_fields_when_patching_me_then_422(client):
    s = login(client)
    client.post("/v1/me/consents", json=GRANT, headers=_h(s))
    for extra in ({"age": 40}, {"land_status": "owner"}):
        assert client.patch("/v1/me", json={"display_name": "H", **extra}, headers=_h(s)).status_code == 422


def _purge(now):
    from app.accounts.purge import purge_pending_accounts
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as session:
            n = await purge_pending_accounts(session, now)
            await session.commit()
            return n

    return asyncio.run(run())


def test_given_a_pending_account_older_than_24h_without_consent_when_purging_then_it_is_deleted(client):
    s = login(client)
    sql("UPDATE users SET created_at = now() - interval '25 hours' WHERE id = $1::uuid", s["user"]["id"])
    assert _purge(dt.datetime.now(dt.UTC)) == 1
    assert sql("SELECT 1 FROM users WHERE id = $1::uuid", s["user"]["id"]) == []


def test_given_a_pending_account_younger_than_24h_when_purging_then_it_is_kept(client):
    s = login(client)
    assert _purge(dt.datetime.now(dt.UTC)) == 0
    assert len(sql("SELECT 1 FROM users WHERE id = $1::uuid", s["user"]["id"])) == 1


def test_given_an_old_account_with_consent_when_purging_then_it_is_kept(client):
    s = login(client)
    client.post("/v1/me/consents", json=GRANT, headers=_h(s))
    sql("UPDATE users SET created_at = now() - interval '48 hours' WHERE id = $1::uuid", s["user"]["id"])
    assert _purge(dt.datetime.now(dt.UTC)) == 0

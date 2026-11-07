"""T022 - /v1/auth/refresh (rotation, reuse -> 401) and /v1/auth/logout (R1-A4)."""
from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login  # noqa: F401


def _refresh(client, token):
    return client.post("/v1/auth/refresh", json={"refresh_token": token})


def test_given_a_refresh_token_when_refreshing_then_a_new_pair_is_returned_and_the_old_token_is_spent(client):
    s = login(client)
    r = _refresh(client, s["refresh_token"])
    assert r.status_code == 200
    body = r.json()
    assert body["refresh_token"] != s["refresh_token"] and body["access_token"]
    assert body["user"]["id"] == s["user"]["id"]


def test_given_a_rotated_token_when_replayed_then_401_and_the_whole_family_is_revoked(client):
    s = login(client)
    new = _refresh(client, s["refresh_token"]).json()
    assert _refresh(client, s["refresh_token"]).status_code == 401
    assert _refresh(client, new["refresh_token"]).status_code == 401
    assert sql("SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL")[0][0] == 0


def test_given_an_unknown_token_when_refreshing_then_401(client):
    assert _refresh(client, "nope").status_code == 401


def test_given_a_refresh_token_when_stored_then_only_its_hash_is_in_the_database(client):
    s = login(client)
    hashes = [r[0] for r in sql("SELECT token_hash FROM refresh_tokens")]
    assert s["refresh_token"] not in hashes


def test_given_a_session_when_logging_out_then_204_and_the_refresh_token_stops_working(client):
    s = login(client)
    r = client.post(
        "/v1/auth/logout", json={"refresh_token": s["refresh_token"]}, headers=auth(s["access_token"])
    )
    assert r.status_code == 204
    assert _refresh(client, s["refresh_token"]).status_code == 401


def test_given_two_devices_when_one_logs_out_then_the_other_session_stays_valid(client):
    a = login(client)
    sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - interval '2 minutes'")
    b = login(client)
    client.post("/v1/auth/logout", json={"refresh_token": a["refresh_token"]}, headers=auth(a["access_token"]))
    assert _refresh(client, b["refresh_token"]).status_code == 200

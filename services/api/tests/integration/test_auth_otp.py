"""T021 - /v1/auth/otp/request and /verify (R1-A1, R1-A2, R1-A3). Hardening cases live in test_otp_hardening.py."""
import datetime as dt

from tests.helpers import sql
from tests.integration._auth_flow import CODE, PHONE, _test_otp, login  # noqa: F401


def _request(client, phone=PHONE):
    return client.post("/v1/auth/otp/request", json={"phone": phone})


def _verify(client, code, phone=PHONE):
    return client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})


def test_given_an_invalid_number_when_requesting_a_code_then_422_phone_invalid(client):
    r = _request(client, "+33612345678")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "phone_invalid"


def test_given_a_local_06_number_when_requesting_then_it_is_normalised_to_e164(client):
    assert _request(client, "0612345678").status_code == 202
    assert sql("SELECT phone_e164 FROM otp_challenges")[0][0] == PHONE


def test_given_known_and_unknown_numbers_when_requesting_then_the_answer_is_identical(client):
    login(client)
    sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - interval '2 minutes'")
    known = _request(client)
    unknown = _request(client, "+212798765432")
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())


def test_given_a_new_user_when_verifying_the_right_code_then_a_pending_account_and_a_session_are_returned(client):
    body = login(client)
    assert {"access_token", "refresh_token", "user", "farms"} <= set(body)
    assert body["user"]["phone"] == PHONE and body["farms"] == []
    assert len(sql("SELECT 1 FROM users WHERE phone_e164=$1", PHONE)) == 1


def test_given_a_session_when_issued_then_the_access_token_lives_about_fifteen_minutes(client):
    body = login(client)
    left = dt.datetime.fromisoformat(body["expires_at"]) - dt.datetime.now(dt.UTC)
    assert dt.timedelta(minutes=14) < left <= dt.timedelta(minutes=15)


def test_given_a_wrong_code_when_verifying_then_400_with_attempts_left(client):
    _request(client)
    r = _verify(client, "111111")
    assert r.status_code == 400
    assert r.json()["detail"] == {"code": "otp_invalid", "attempts_left": 2}


def test_given_an_expired_code_when_verifying_then_410_otp_expired(client):
    _request(client)
    sql("UPDATE otp_challenges SET expires_at = now() - interval '1 second'")
    r = _verify(client, CODE)
    assert r.status_code == 410
    assert r.json()["detail"]["code"] == "otp_expired"


def test_given_three_wrong_codes_when_verifying_then_423_with_a_five_minute_retry_after(client):
    _request(client)
    _verify(client, "111111")
    _verify(client, "111111")
    r = _verify(client, "111111")
    assert r.status_code == 423
    assert r.json()["detail"] == {"code": "otp_locked", "retry_after": 300}
    row = sql("SELECT locked_until - now() FROM otp_challenges")[0][0]
    assert dt.timedelta(minutes=4, seconds=50) < row <= dt.timedelta(minutes=5)


def test_given_an_existing_account_when_logging_in_again_then_the_same_user_is_returned_without_duplicate(client):
    first = login(client)
    sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - interval '2 minutes'")
    second = login(client)
    assert second["user"]["id"] == first["user"]["id"]
    assert len(sql("SELECT 1 FROM users WHERE phone_e164=$1", PHONE)) == 1


def test_given_a_member_of_a_farm_when_logging_in_then_farms_list_the_id_and_role(client, make_farm):
    first = login(client)
    import uuid

    farm = make_farm({uuid.UUID(first["user"]["id"]): "owner"})
    sql("UPDATE otp_challenges SET last_sent_at = last_sent_at - interval '2 minutes'")
    again = login(client)
    assert again["farms"] == [{"id": str(farm), "role": "owner"}]


def test_given_a_code_when_requested_then_it_is_stored_hashed_only(client):
    _request(client)
    h = sql("SELECT code_hash FROM otp_challenges")[0][0]
    assert h.startswith("$argon2id$") and CODE not in h

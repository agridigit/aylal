"""T035 - PATCH /v1/me stores the language on the account (R2-A3)."""
import pytest

from tests.helpers import auth, sql
from tests.integration._auth_flow import _test_otp, login  # noqa: F401


def test_given_a_session_when_getting_me_then_the_profile_is_returned(client):
    s = login(client)
    r = client.get("/v1/me", headers=auth(s["access_token"]))
    assert r.status_code == 200
    assert {"id", "phone", "status", "language", "display_name"} <= set(r.json())


@pytest.mark.parametrize("language", ["ary", "ar", "fr"])
def test_given_a_user_when_changing_language_then_it_is_stored_on_the_account(client, language):
    s = login(client)
    r = client.patch("/v1/me", json={"language": language}, headers=auth(s["access_token"]))
    assert r.status_code == 200 and r.json()["language"] == language
    assert sql("SELECT language FROM users WHERE id = $1::uuid", s["user"]["id"])[0][0] == language
    assert client.get("/v1/me", headers=auth(s["access_token"])).json()["language"] == language


def test_given_an_unknown_language_when_patching_then_422_and_nothing_changes(client):
    s = login(client)
    client.patch("/v1/me", json={"language": "fr"}, headers=auth(s["access_token"]))
    r = client.patch("/v1/me", json={"language": "en"}, headers=auth(s["access_token"]))
    assert r.status_code == 422
    assert sql("SELECT language FROM users WHERE id = $1::uuid", s["user"]["id"])[0][0] == "fr"


def test_given_no_session_when_patching_me_then_401(client):
    assert client.patch("/v1/me", json={"language": "fr"}).status_code == 401

"""T043 - encryption in transit and credentials at rest on the server side (AC3.6, FR-017)."""
import httpx

from tests.helpers import sql

PROXY = "proxy"


def test_given_the_database_when_checking_password_hashing_then_scram_sha_256_is_active(
    clean_db,
) -> None:
    assert sql("SHOW password_encryption")[0][0] == "scram-sha-256"
    stored = sql("SELECT rolpassword FROM pg_authid WHERE rolname = 'aylal'")[0][0]
    assert stored.startswith("SCRAM-SHA-256$")


def test_given_the_proxy_when_calling_the_api_over_tls_then_it_answers(clean_db) -> None:
    r = httpx.get(f"https://{PROXY}/v1/health", verify=False)
    assert r.status_code in {200, 503}
    assert r.json()["status"] in {"ok", "degraded"}


def test_given_the_proxy_when_calling_in_clear_text_then_it_refuses_to_serve_data(clean_db) -> None:
    try:
        r = httpx.get(f"http://{PROXY}/v1/health", follow_redirects=False)
    except httpx.TransportError:
        return  # port closed: clear text refused
    assert r.status_code in {301, 302, 307, 308}
    assert r.headers["location"].startswith("https://")
    assert "status" not in r.text

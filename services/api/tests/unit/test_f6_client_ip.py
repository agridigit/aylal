"""T009 - G5: client_ip() extracted to app.auth.client_ip; forwarded headers only count from a trusted peer."""
from types import SimpleNamespace

import pytest


def _req(peer, headers):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


@pytest.fixture
def trusted(monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.1.1.1/32")


def test_given_an_untrusted_peer_when_xff_is_forged_then_it_is_ignored(trusted):
    from app.auth.client_ip import client_ip

    assert client_ip(_req("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})) == "203.0.113.9"


def test_given_a_trusted_peer_then_the_rightmost_untrusted_hop_is_used(trusted):
    from app.auth.client_ip import client_ip

    assert client_ip(_req("10.1.1.1", {"x-forwarded-for": "9.9.9.9, 198.51.100.7, 10.1.1.1"})) == "198.51.100.7"


def test_given_a_trusted_peer_without_headers_then_no_shared_bucket(trusted):
    from app.auth.client_ip import client_ip

    assert client_ip(_req("10.1.1.1", {})) is None


def test_given_the_auth_router_then_it_reuses_the_extracted_function():
    from app.auth import client_ip as extracted
    from app.routers import auth

    assert auth.client_ip is extracted.client_ip

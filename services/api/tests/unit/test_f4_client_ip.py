"""T014 - G6: F4 routes use the shared client_ip(); X-Forwarded-For only counts from a trusted proxy."""
from types import SimpleNamespace

import pytest

ROUTERS = ["irrigation_systems", "irrigation_advice", "irrigation_events", "consumption", "water_analyses"]


def _req(peer, headers):
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


@pytest.fixture
def trusted(monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.1.1.1/32")


@pytest.mark.parametrize("module", ROUTERS)
def test_given_an_f4_router_then_it_reuses_the_shared_client_ip(module):
    import importlib

    from app.auth import client_ip as shared

    assert importlib.import_module(f"app.routers.{module}").client_ip is shared.client_ip


def test_given_a_forged_header_from_an_untrusted_peer_then_the_limiter_key_uses_the_socket_peer(trusted):
    from app.irrigation.limits import limiter_key

    assert limiter_key("record", _req("203.0.113.9", {"x-forwarded-for": "1.2.3.4"}), user="u") == limiter_key("record", _req("203.0.113.9", {}), user="u")


def test_given_a_trusted_proxy_then_the_forwarded_client_is_part_of_the_key(trusted):
    from app.irrigation.limits import limiter_key

    a = limiter_key("record", _req("10.1.1.1", {"x-forwarded-for": "198.51.100.7, 10.1.1.1"}), user="u")
    b = limiter_key("record", _req("10.1.1.1", {"x-forwarded-for": "198.51.100.8, 10.1.1.1"}), user="u")
    assert a != b


def test_given_the_existing_client_ip_behaviour_then_it_is_unchanged(trusted):
    from app.auth.client_ip import client_ip

    assert client_ip(_req("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})) == "203.0.113.9"
    assert client_ip(_req("10.1.1.1", {"x-forwarded-for": "9.9.9.9, 198.51.100.7, 10.1.1.1"})) == "198.51.100.7"

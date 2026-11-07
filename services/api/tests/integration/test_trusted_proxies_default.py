"""Trusted proxies fail closed: the compose default is an exact /32, and an all-trusted chain falls back to the peer."""
import ipaddress
import os
import re
from pathlib import Path
from types import SimpleNamespace

from app.routers.auth import client_ip

COMPOSE = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "docker-compose.yml"


def test_given_the_compose_file_then_the_default_trusted_proxy_is_one_exact_address_not_a_private_range() -> None:
    m = re.search(r"AYLAL_TRUSTED_PROXIES: \$\{AYLAL_TRUSTED_PROXIES:-([^}]*)\}", COMPOSE.read_text(encoding="utf-8"))
    assert m is not None
    entries = [e.strip() for e in m.group(1).split(",") if e.strip()]
    for entry in entries:
        net = ipaddress.ip_network(entry, strict=False)
        assert net.num_addresses == 1, f"{entry} trusts more than one host"


def test_given_the_api_port_then_it_is_not_published_on_all_host_interfaces() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert '"8000:8000"' not in text


def _req(peer: str, headers: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_given_every_forwarded_hop_is_trusted_when_resolving_then_the_socket_peer_is_used(monkeypatch) -> None:
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.0.0.5,10.0.0.6")
    assert client_ip(_req("10.0.0.5", {"x-forwarded-for": "10.0.0.6, 10.0.0.5"})) == "10.0.0.5"


def test_given_an_untrusted_hop_when_resolving_then_it_is_still_the_client(monkeypatch) -> None:
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.0.0.5")
    assert client_ip(_req("10.0.0.5", {"x-forwarded-for": "203.0.113.4, 10.0.0.5"})) == "203.0.113.4"

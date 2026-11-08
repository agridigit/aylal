"""T026 - G6: Redis rate limiter on costly F3 routes (429 + Retry-After); X-Forwarded-For counts only from a trusted proxy."""
import io

import pytest

from tests.helpers import auth
from tests.integration._f3 import flush_redis, seed_zone, world3  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512


@pytest.fixture(autouse=True)
def _flush():
    flush_redis()


def _hit(client, kind, w, h, extra=None):
    f = f"/v1/farms/{w['farm_a']}"
    hh = {**h, **(extra or {})}
    if kind == "photo":
        return client.post(f"{f}/zones/{w['zone']}/observations/photo", headers=hh, files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")})
    if kind == "reprocess":
        return client.post(f"{f}/parcels/{w['a1']}/vigor/reprocess", headers=hh)
    if kind == "series":
        return client.get(f"{f}/parcels/{w['a1']}/vigor", headers=hh)
    if kind == "compare":
        return client.get(f"{f}/parcels/{w['a1']}/vigor/compare", headers=hh)
    return client.get(f"{f}/summary/today", headers=hh)


@pytest.mark.parametrize("kind", ["photo", "reprocess", "series", "compare", "summary"])
def test_given_a_costly_route_when_the_hourly_limit_is_exceeded_then_429_with_retry_after(client, token_for, world3, kind):
    w = {**world3, "zone": seed_zone(world3["farm_a"], world3["a1"])}
    h = auth(token_for(w["owner"]))
    first = _hit(client, kind, w, h)
    assert first.status_code in (200, 201, 202), first.text
    codes = [first.status_code]
    for _ in range(300):
        codes.append(_hit(client, kind, w, h).status_code)
        if codes[-1] == 429:
            break
    assert 429 in codes, "no limit reached after 300 calls"
    r = _hit(client, kind, w, h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_given_a_forged_xff_from_an_untrusted_peer_then_it_does_not_change_the_limiter_key(client, token_for, world3, monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.9.9.9/32")  # the TestClient peer is not in it
    w = {**world3, "zone": seed_zone(world3["farm_a"], world3["a1"])}
    h = auth(token_for(w["owner"]))
    assert _hit(client, "summary", w, h).status_code == 200
    limited = None
    for i in range(300):
        r = _hit(client, "summary", w, h, {"X-Forwarded-For": f"203.0.113.{i % 250}"})
        if r.status_code == 429:
            limited = i
            break
    assert limited is not None, "rotating a forged X-Forwarded-For must not evade the limiter"


def test_given_a_trusted_proxy_then_the_forwarded_client_ip_is_taken_into_account(client, token_for, world3, monkeypatch):
    from types import SimpleNamespace

    from app.monitoring.limits import limiter_key

    w = world3
    assert _hit(client, "summary", {**w, "zone": None}, auth(token_for(w["owner"]))).status_code == 200  # the route exists
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.1.1.1/32")

    def req(ip):
        return SimpleNamespace(client=SimpleNamespace(host="10.1.1.1"), headers={"x-forwarded-for": f"{ip}, 10.1.1.1"})

    assert limiter_key("summary", req("198.51.100.1"), user="u") != limiter_key("summary", req("198.51.100.2"), user="u")

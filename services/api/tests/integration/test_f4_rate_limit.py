"""T030 - G6: Redis rate limiter on costly F4 routes (429 + Retry-After); X-Forwarded-For counts only from a trusted proxy; no FLUSHDB."""
import uuid

import pytest

from tests.helpers import auth
from tests.integration._f4 import flush_f4_redis, world4  # noqa: F401


@pytest.fixture(autouse=True)
def _flush():
    flush_f4_redis()


def _hit(client, kind, w, h, extra=None):
    f, p = f"/v1/farms/{w['farm_a']}", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}"
    hh = {**h, **(extra or {})}
    if kind == "record":
        return client.post(f"{p}/irrigation/events", headers=hh, json={"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 5})
    if kind == "history":
        return client.get(f"{p}/irrigation/events", headers=hh)
    if kind == "consumption":
        return client.get(f"{f}/irrigation/consumption", headers=hh)
    return client.post(f"{p}/water-analyses", headers=hh, json={"id": str(uuid.uuid4()), "ec_ds_m": 1.0, "analysed_on": "2026-06-01"})


@pytest.mark.parametrize("kind", ["record", "history", "consumption", "analysis"])
def test_given_a_costly_route_when_the_hourly_limit_is_exceeded_then_429_with_retry_after(client, token_for, world4, kind):
    w = world4
    h = auth(token_for(w["owner"]))
    first = _hit(client, kind, w, h)
    assert first.status_code in (200, 201), first.text
    codes = [first.status_code]
    for _ in range(400):
        codes.append(_hit(client, kind, w, h).status_code)
        if codes[-1] == 429:
            break
    assert 429 in codes, "no limit reached after 400 calls"
    r = _hit(client, kind, w, h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_given_a_forged_xff_from_an_untrusted_peer_then_it_does_not_change_the_limiter_key(client, token_for, world4, monkeypatch):
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.9.9.9/32")  # the TestClient peer is not in it
    w = world4
    h = auth(token_for(w["owner"]))
    assert _hit(client, "consumption", w, h).status_code == 200
    limited = None
    for i in range(400):
        if _hit(client, "consumption", w, h, {"X-Forwarded-For": f"203.0.113.{i % 250}"}).status_code == 429:
            limited = i
            break
    assert limited is not None, "rotating a forged X-Forwarded-For must not evade the limiter"


def test_given_a_trusted_proxy_then_the_forwarded_client_ip_is_taken_into_account(client, token_for, world4, monkeypatch):
    from types import SimpleNamespace

    from app.irrigation.limits import limiter_key

    w = world4
    assert _hit(client, "consumption", w, auth(token_for(w["owner"]))).status_code == 200  # the route exists
    monkeypatch.setenv("AYLAL_TRUSTED_PROXIES", "10.1.1.1/32")

    def req(ip):
        return SimpleNamespace(client=SimpleNamespace(host="10.1.1.1"), headers={"x-forwarded-for": f"{ip}, 10.1.1.1"})

    assert limiter_key("consumption", req("198.51.100.1"), user="u") != limiter_key("consumption", req("198.51.100.2"), user="u")


def test_given_the_limiter_keys_then_they_are_prefixed_f4_and_never_collide_with_f3():
    from types import SimpleNamespace

    from app.irrigation.limits import limiter_key

    key = limiter_key("record", SimpleNamespace(client=SimpleNamespace(host="203.0.113.9"), headers={}), user="u")
    assert str(key).startswith("f4:")

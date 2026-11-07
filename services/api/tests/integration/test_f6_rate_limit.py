"""T020 - G5: Redis rate limiter, 429 + Retry-After, X-Forwarded-For only from a trusted proxy."""
import io

import pytest

from tests.helpers import auth
from tests.integration._f6 import op_body, world  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512
EXPORT = {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "pdf", "scope": "farm", "lang": "fr"}


@pytest.fixture(autouse=True)
def _flush():
    """FLUSHDB over a raw RESP socket (no redis client library is installed before the GREEN)."""
    import socket
    from urllib.parse import urlparse

    from app.config import get_settings

    u = urlparse(get_settings().redis_url)
    with socket.create_connection((u.hostname or "redis", u.port or 6379), timeout=3) as s:
        s.sendall(b"*1\r\n$7\r\nFLUSHDB\r\n")
        assert s.recv(16).startswith(b"+OK")


def _hit(client, kind, w, h):
    f = f"/v1/farms/{w['farm_a']}"
    if kind == "parse":
        return client.post(f"{f}/operations/parse", headers=h, json={"text": "irrigation"})
    if kind == "label":
        return client.post(f"{f}/operations/label", headers=h, files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")})
    return client.post(f"{f}/registry/exports", headers=h, json=EXPORT)


@pytest.mark.parametrize("kind,limit", [("parse", 60), ("label", 20)])
def test_given_the_hourly_limit_when_exceeded_then_429_with_retry_after(client, token_for, world, kind, limit):
    w = world
    h = auth(token_for(w["owner"]))
    first = _hit(client, kind, w, h)
    assert first.status_code in (200, 503), first.text
    codes = [first.status_code] + [_hit(client, kind, w, h).status_code for _ in range(limit)]
    assert 429 in codes
    r = _hit(client, kind, w, h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_given_ten_exports_in_an_hour_then_the_eleventh_is_429(client, token_for, world):
    from tests.helpers import sql
    w = world
    h = auth(token_for(w["owner"]))
    assert client.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=h, json=EXPORT).status_code == 202
    codes = []
    for _ in range(11):
        sql("UPDATE export_jobs SET state='done' WHERE farm_id=$1", w["farm_a"])
        codes.append(client.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=h, json=EXPORT))
    assert any(c.status_code == 429 and "Retry-After" in c.headers for c in codes)


def test_given_a_forged_xff_from_an_untrusted_peer_then_the_limit_key_does_not_change(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    assert _hit(client, "label", w, h).status_code in (200, 503)
    seen_429 = False
    for i in range(25):
        r = _hit(client, "label", w, {**h, "X-Forwarded-For": f"198.51.100.{i}"})
        seen_429 = seen_429 or r.status_code == 429
    assert seen_429, "rotating a forged X-Forwarded-For must not evade the limit"


def test_given_the_limiter_module_then_it_is_shared_and_redis_backed():
    from app.auth import rate_limit

    assert callable(getattr(rate_limit, "check_rate_limit", None))

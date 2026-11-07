"""Minimal HS256 JWT (no extra dependency). Claims: sub, farm_ids, roles, aud, iat, exp."""
import base64
import datetime as dt
import hashlib
import hmac
import json
import uuid
from typing import Any

TTL = dt.timedelta(hours=12)
ACCESS_TTL = dt.timedelta(minutes=15)  # OTP sessions: short access token, long-lived rotating refresh token


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(signing_input: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())


def issue_token(
    user_id: uuid.UUID, secret: str, farm_ids: list[str], roles: dict[str, str],
    ttl: dt.timedelta = TTL,
) -> tuple[str, dt.datetime]:
    now = dt.datetime.now(dt.UTC)
    expires = now + ttl
    claims = {
        "sub": str(user_id),
        "aud": "powersync",
        "farm_ids": farm_ids,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    signing_input = f"{head}.{_b64(json.dumps(claims).encode())}"
    return f"{signing_input}.{_sign(signing_input, secret)}", expires


def verify_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        head, body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(f"{head}.{body}", secret)):
            return None
        if json.loads(_unb64(head)).get("alg") != "HS256":
            return None
        claims: dict[str, Any] = json.loads(_unb64(body))
        if claims["exp"] < dt.datetime.now(dt.UTC).timestamp():
            return None
        uuid.UUID(claims["sub"])
        return claims
    except (ValueError, KeyError, TypeError):
        return None

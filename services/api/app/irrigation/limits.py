"""Rate limits of the costly F4 routes (Redis, per hour). The key uses the shared client_ip(): X-Forwarded-For counts only
from a trusted proxy, so a forged header never changes the key. Keys are prefixed `f4:`."""
import uuid
from typing import Any

from fastapi import Request

from app.auth.client_ip import client_ip
from app.auth.rate_limit import check_rate_limit

HOURLY: dict[str, int] = {"record": 60, "history": 120, "consumption": 120, "analysis": 60}


def limiter_key(kind: str, request: Any, *, user: Any, farm: Any = None) -> str:
    return f"f4:{kind}:{farm or '-'}:{user}:{client_ip(request) or '-'}"


async def limit(kind: str, request: Request, user: uuid.UUID, farm: uuid.UUID) -> None:
    """Count one hit; over the limit -> 429 + Retry-After."""
    await check_rate_limit(limiter_key(kind, request, user=user, farm=farm), HOURLY[kind])

"""Rate limits of the costly F3 routes (Redis, per hour). The key uses the shared client_ip(): X-Forwarded-For counts only
from a trusted proxy, so a forged header never changes the key."""
import uuid
from typing import Any

from fastapi import Request

from app.auth.client_ip import client_ip
from app.auth.rate_limit import check_rate_limit

HOURLY: dict[str, int] = {"photo": 30, "reprocess": 10, "series": 120, "compare": 60, "summary": 120}


def limiter_key(kind: str, request: Any, *, user: Any, farm: Any = None) -> str:
    return f"f3:{kind}:{farm or '-'}:{user}:{client_ip(request) or '-'}"


async def limit(kind: str, request: Request, user: uuid.UUID, farm: uuid.UUID) -> None:
    """Count one hit; over the limit -> 429 + Retry-After."""
    await check_rate_limit(limiter_key(kind, request, user=user, farm=farm), HOURLY[kind])

"""Scope-bound cache keys and ETags (G2). The key carries farm, role, a digest of the VISIBLE parcels, the local day and a data
version, so two scopes never share an entry and an assignment, archive, role or day change changes the key. No user id is in
the key: staff of the same role share an entry; workers with the same parcels share the same content."""
import datetime as dt
import hashlib
import uuid
from collections.abc import Iterable
from typing import Any

import redis.asyncio as redis

from app.config import get_settings


def _digest(parcel_ids: Iterable[uuid.UUID]) -> str:
    return hashlib.sha256(",".join(sorted(str(p) for p in parcel_ids)).encode()).hexdigest()


def advice_cache_key(farm_id: uuid.UUID, role: str, parcel_ids: Iterable[uuid.UUID], day: dt.date, data_version: int) -> str:
    """irr:{farm}:{role}:{sha256(sorted visible ids)}:{local date}:{data_version}"""
    return f"irr:{farm_id}:{role}:{_digest(parcel_ids)}:{day.isoformat()}:{data_version}"


def advice_etag(farm_id: uuid.UUID, role: str, parcel_ids: Iterable[uuid.UUID], day: dt.date, data_version: int) -> str:
    """Opaque tag bounded to the scope (no id is readable in it)."""
    return hashlib.sha256(advice_cache_key(farm_id, role, parcel_ids, day, data_version).encode()).hexdigest()[:32]


def content_etag(scope_tag: str, content: Any) -> str:
    """ETag of a response: the scope plus the CONTENT served, so a change of an invisible parcel never moves it."""
    import json

    return hashlib.sha256((scope_tag + json.dumps(content, sort_keys=True, default=str)).encode()).hexdigest()[:32]


def _client() -> Any:
    return redis.from_url(get_settings().redis_url)  # type: ignore[no-untyped-call]  # one client per call: callers live on different event loops


async def get_data_version(farm_id: uuid.UUID) -> int:
    client = _client()
    try:
        return int(await client.get(f"irrver:{farm_id}") or 0)
    except redis.RedisError:
        return 0
    finally:
        await client.aclose()


async def bump_data_version(farm_id: uuid.UUID) -> int:
    """Invalidate every cached view of the farm."""
    client = _client()
    try:
        return int(await client.incr(f"irrver:{farm_id}"))
    except redis.RedisError:
        return 0
    finally:
        await client.aclose()

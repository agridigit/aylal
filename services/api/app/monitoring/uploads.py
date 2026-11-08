"""Opaque objects (G6): clients never name a storage key. Photos are deposited first and referenced by a server-issued
`photo_id` bound to (farm, user), single use, valid 24 hours; maps are served as signed URLs of 15 minutes."""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.monitoring_limits import LIMITS
from app.operations.storage import MAX_PRESIGN_SECONDS, ObjectStorage, get_storage

UPLOAD_HOURS = 24


class InvalidObjectRef(Exception):
    """photo_id unknown, of another farm or user, consumed or expired: always the same error (no oracle)."""


def vigor_map_key(farm_id: uuid.UUID, object_id: uuid.UUID) -> str:
    return f"farms/{farm_id}/vigor/{object_id}.png"


def zone_photo_key(farm_id: uuid.UUID, object_id: uuid.UUID) -> str:
    return f"farms/{farm_id}/zone-photos/{object_id}"


def sniff_image(data: bytes) -> str | None:
    """Content type from the signature (never from the client): JPEG or WebP only."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def deposit_photo(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, data: bytes, storage: ObjectStorage | None = None
) -> uuid.UUID:
    """Store the photo under a server key and issue its opaque id. The caller has checked size and signature."""
    photo_id = uuid.uuid4()
    key = zone_photo_key(farm_id, photo_id)
    await (storage or get_storage()).put(key, data, sniff_image(data) or "application/octet-stream")
    await session.execute(
        text(
            "INSERT INTO observation_uploads (id, farm_id, user_id, object_key, expires_at)"
            " VALUES (:i, :f, :u, :k, now() + make_interval(hours => :h))"
        ),
        {"i": photo_id, "f": farm_id, "u": user_id, "k": key, "h": UPLOAD_HOURS},
    )
    return photo_id


async def consume_photo(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, photo_id: uuid.UUID) -> str:
    """Single use: returns the server key, or raises InvalidObjectRef (same error for every failure)."""
    row = (
        await session.execute(
            text(
                "UPDATE observation_uploads SET consumed_at = now() WHERE id = :i AND farm_id = :f AND user_id = :u"
                " AND consumed_at IS NULL AND expires_at > now() RETURNING object_key"
            ),
            {"i": photo_id, "f": farm_id, "u": user_id},
        )
    ).first()
    if row is None:
        raise InvalidObjectRef
    return str(row[0])


def signed_map_url(key: str, storage: ObjectStorage | None = None) -> str:
    """Signed URL of 15 minutes. The slashes of the key are sent as %2F (the storage decodes them before checking the
    signature), so the URL does not spell out the folder layout of the farm's objects."""
    store = storage or get_storage()
    url = store.presign_get(key, MAX_PRESIGN_SECONDS)
    return url.replace(f"/{store.bucket}/{key}", f"/{store.bucket}/{key.replace('/', '%2F')}", 1)


def photo_cap() -> int:
    return LIMITS["photo_bytes"]

"""Label photo (G1): the server names the object, the client only ever holds an opaque `label_photo_id`.

The object key is generated here (`farms/{farm_id}/labels/{uuid}`), bound to (farm, user), used once and purged
after 24 h when never attached. No key or URL is read from a client body. Recognition goes through an optional
port (AYLAL_VISION_URL); when it is empty the recognizer is unavailable and the caller falls back to manual entry.
"""
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.operation_limits import LIMITS


class InvalidObjectRef(Exception):
    """Unknown, foreign (other farm or user) or already consumed reference: always the same answer."""


def sniff(data: bytes) -> str | None:
    """Image type from the signature (JPEG or WebP); the declared content type is not trusted."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def read_object(key: str) -> bytes:  # pragma: no cover - object storage adapter, wired with the label story
    raise NotImplementedError("object storage is not wired yet")


def recognizer_available() -> bool:
    return bool(get_settings().vision_url)


async def register_upload(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, size: int) -> uuid.UUID:
    """Record a photo for (farm, user) under a server-generated key; returns the opaque label_photo_id."""
    if size > LIMITS["label_bytes"]:
        raise ValueError("photo too large")
    upload_id = uuid.uuid4()
    key = f"farms/{farm_id}/labels/{uuid.uuid4()}"
    await session.execute(
        text("INSERT INTO label_uploads (id, farm_id, user_id, object_key) VALUES (:i, :f, :u, :k)"),
        {"i": upload_id, "f": farm_id, "u": user_id, "k": key},
    )
    return upload_id


async def consume(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, label_id: Any) -> str:
    """Resolve a label_photo_id on (id, farm_id, user_id), consume it once and return the server-side key."""
    try:
        wanted = uuid.UUID(str(label_id))
    except ValueError as e:
        raise InvalidObjectRef from e
    row = (
        await session.execute(
            text(
                "UPDATE label_uploads SET consumed_at = now() WHERE id = :i AND farm_id = :f AND user_id = :u"
                " AND consumed_at IS NULL AND created_at > now() - interval '24 hours' RETURNING object_key"
            ),
            {"i": wanted, "f": farm_id, "u": user_id},
        )
    ).first()
    if row is None:
        raise InvalidObjectRef
    return str(row[0])

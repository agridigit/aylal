"""Label photo (G1): the server names the object, the client only ever holds an opaque `label_photo_id`.

The object key is generated here (`farms/{farm_id}/labels/{uuid}`), bound to (farm, user), used once and purged
after 24 h when never attached. No key or URL is read from a client body. Recognition goes through an optional
port (AYLAL_VISION_URL); when it is empty the recognizer is unavailable and the caller falls back to manual entry.
"""
import asyncio
import json
import urllib.request
import uuid
from typing import Any, Protocol

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


class RecognizerUnavailable(Exception):
    """The recognition provider is not configured or did not answer: the caller falls back to name search."""


class LabelRecognizer(Protocol):
    """Port: a photo in, candidate products out ({product_id, name, confidence}); never records anything."""

    async def recognize(self, data: bytes) -> list[dict[str, Any]]: ...


class _Unavailable:
    async def recognize(self, data: bytes) -> list[dict[str, Any]]:
        raise RecognizerUnavailable


class HttpRecognizer:
    """Adapter for an operator-configured provider (AYLAL_VISION_URL); nothing external is ever the default."""

    def __init__(self, url: str) -> None:
        self.url = url

    def _post(self, data: bytes) -> list[dict[str, Any]]:
        request = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read(1_000_000))
        return list(body.get("candidates", [])) if isinstance(body, dict) else []

    async def recognize(self, data: bytes) -> list[dict[str, Any]]:
        try:
            return await asyncio.to_thread(self._post, data)
        except (OSError, ValueError) as e:
            raise RecognizerUnavailable from e


def get_recognizer() -> LabelRecognizer:
    """FastAPI dependency: the configured provider, or an unavailable one when AYLAL_VISION_URL is empty."""
    url = get_settings().vision_url
    return HttpRecognizer(url) if url else _Unavailable()


async def catalogue_candidates(session: AsyncSession, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only candidates that are products of the current (not expired) catalogue; names come from the catalogue."""
    out: list[dict[str, Any]] = []
    for item in raw[:10]:
        try:
            pid = uuid.UUID(str(item.get("product_id")))
        except ValueError:
            continue
        name = (
            await session.execute(text("SELECT name FROM phyto_products WHERE id = :i AND expired_at IS NULL"), {"i": pid})
        ).scalar()
        if name is not None:
            confidence = item.get("confidence")
            out.append({"product_id": str(pid), "name": name, "confidence": float(confidence) if isinstance(confidence, (int, float)) else None})
    return out


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

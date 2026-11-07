"""Dictation analysis (R5): the VoiceParser port. Text only; audio never reaches the server.

The port receives the text and the parcels visible to the caller (`id`, `name`), nothing else, and proposes a
draft. It never records anything: the farmer confirms on the form. AYLAL_NLU_URL empty -> unavailable (no
connection is ever made, nothing external is the default).
"""
import asyncio
import json
import urllib.request
import uuid
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.operations.access import STAFF


class ParserUnavailable(Exception):
    """No provider configured or it did not answer: the caller falls back to the empty form."""


class VoiceParser(Protocol):
    async def parse(self, text: str, *, parcels: list[dict[str, str]]) -> dict[str, Any]: ...


class _Unavailable:
    async def parse(self, text: str, *, parcels: list[dict[str, str]]) -> dict[str, Any]:
        raise ParserUnavailable


class HttpVoiceParser:
    """Adapter for an operator-configured provider (AYLAL_NLU_URL)."""

    def __init__(self, url: str) -> None:
        self.url = url

    def _post(self, payload: bytes) -> dict[str, Any]:
        request = urllib.request.Request(self.url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read(1_000_000))
        if not isinstance(body, dict):
            raise TypeError("invalid_nlu_answer")
        return body

    async def parse(self, text: str, *, parcels: list[dict[str, str]]) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(self._post, json.dumps({"text": text, "parcels": parcels}).encode())
        except (OSError, ValueError, TypeError) as e:
            raise ParserUnavailable from e


def get_voice_parser() -> VoiceParser:
    """FastAPI dependency: the configured provider, or an unavailable one when AYLAL_NLU_URL is empty."""
    url = get_settings().nlu_url
    return HttpVoiceParser(url) if url else _Unavailable()


async def visible_parcels(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str) -> list[dict[str, str]]:
    query = "SELECT p.id, p.name FROM parcels p WHERE p.farm_id = :f AND p.archived_at IS NULL"
    if role not in STAFF:
        query += (
            " AND EXISTS (SELECT 1 FROM worker_parcels w WHERE w.farm_id = p.farm_id AND w.parcel_id = p.id AND w.user_id = :u)"
        )
    rows = (await session.execute(text(query + " ORDER BY p.name, p.id"), {"f": farm_id, "u": user_id})).mappings().all()
    return [{"id": str(r["id"]), "name": r["name"]} for r in rows]


def sanitise(raw: dict[str, Any], visible: set[str]) -> dict[str, Any]:
    """Draft shaped for the client: parcels the caller cannot see are dropped from the draft and from the candidates."""
    draft = dict(raw.get("draft") or {})
    if "parcel_ids" in draft:
        kept = [p for p in draft["parcel_ids"] if str(p) in visible]
        if kept:
            draft["parcel_ids"] = kept
        else:
            del draft["parcel_ids"]
    ambiguous = [
        {"field": a["field"], "candidates": [c for c in a.get("candidates", []) if str(c) in visible]}
        for a in raw.get("ambiguous") or []
    ]
    return {"understood": bool(draft), "requires_confirmation": True, "draft": draft, "ambiguous": ambiguous}

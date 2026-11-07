"""Refresh token rotation and reuse detection (pure rules; persistence lives in the router)."""
import dataclasses
import datetime as dt
import hashlib
import secrets
import uuid
from typing import Literal


@dataclasses.dataclass(frozen=True)
class TokenRecord:
    id: uuid.UUID
    family_id: uuid.UUID
    token_hash: str
    rotated_at: dt.datetime | None = None
    revoked_at: dt.datetime | None = None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def evaluate(record: TokenRecord, now: dt.datetime) -> Literal["rotate", "reuse", "revoked"]:
    if record.revoked_at is not None:
        return "revoked"
    if record.rotated_at is not None:
        return "reuse"
    return "rotate"


def revoke_family(records: list[TokenRecord], family_id: uuid.UUID, now: dt.datetime) -> list[TokenRecord]:
    return [
        dataclasses.replace(r, revoked_at=r.revoked_at or now) if r.family_id == family_id else r
        for r in records
    ]


def rotate(old: TokenRecord, now: dt.datetime) -> tuple[TokenRecord, TokenRecord, str]:
    raw = new_token()
    new = TokenRecord(id=uuid.uuid4(), family_id=old.family_id, token_hash=hash_token(raw))
    return dataclasses.replace(old, rotated_at=now), new, raw

"""Account profile and consents (R2, R3). Everything is scoped to the authenticated user."""
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db.models import Consent, User
from app.db.session import get_session

router = APIRouter(prefix="/me")
DATA_POLICY = "data_policy"
LANGUAGES = {"ary", "ar", "fr"}


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")  # minimal profile: name and language only
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    language: str | None = None


class ConsentGrant(BaseModel):
    purpose: str = Field(min_length=1, max_length=80)
    text_version: str = Field(min_length=1, max_length=40)


def _me(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id), "phone": u.phone_e164, "status": u.status,
        "language": u.language, "display_name": u.display_name,
    }


async def _user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


@router.get("")
async def get_me(
    user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return _me(await _user(session, user_id))


@router.patch("")
async def patch_me(
    body: ProfilePatch, user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    user = await _user(session, user_id)
    if body.language is not None and body.language not in LANGUAGES:
        raise HTTPException(status_code=422, detail={"code": "language_invalid"})
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(status_code=422, detail={"code": "display_name_invalid"})
        active = (
            await session.execute(
                select(Consent.id)
                .where(Consent.user_id == user_id, Consent.purpose == DATA_POLICY, Consent.withdrawn_at.is_(None))
                .limit(1)
            )
        ).first()
        if active is None:
            raise HTTPException(status_code=403, detail={"code": "consent_required"})
        user.display_name = name
        user.status = "active"
    if body.language is not None:
        user.language = body.language
    await session.commit()
    return _me(user)


def _consent_json(c: Consent) -> dict[str, Any]:
    return {
        "purpose": c.purpose,
        "text_version": c.text_version,
        "granted_at": c.granted_at.isoformat(),
        "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
    }


@router.post("/consents", status_code=201)
async def grant_consent(
    body: ConsentGrant, user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    c = Consent(id=uuid.uuid4(), user_id=user_id, purpose=body.purpose, text_version=body.text_version)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return _consent_json(c)


@router.get("/consents")
async def list_consents(
    user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    rows = await session.execute(select(Consent).where(Consent.user_id == user_id).order_by(Consent.granted_at))
    return [_consent_json(c) for c in rows.scalars().all()]


@router.delete("/consents/{purpose}", status_code=204)
async def withdraw_consent(
    purpose: str, user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    await session.execute(
        update(Consent)
        .where(Consent.user_id == user_id, Consent.purpose == purpose, Consent.withdrawn_at.is_(None))
        .values(withdrawn_at=dt.datetime.now(dt.UTC))
    )
    await session.commit()
    return Response(status_code=204)

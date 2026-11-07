"""Phone + one-time code authentication (contracts/auth-otp.md)."""
import datetime as dt
import hashlib
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import issue_token
from app.auth.otp import TEST_CODE, ConsoleSender, check_code, hash_code, new_code
from app.config import get_settings
from app.db.models import FarmMember, OtpChallenge, RefreshToken, User
from app.db.session import get_session
from app.domain.otp_policy import OTP_LOCK_SECONDS, OtpState, is_locked, register_failure
from app.domain.phone import normalize_phone

router = APIRouter(prefix="/auth/otp")
OTP_TTL = dt.timedelta(minutes=5)
sender = ConsoleSender()


class OtpRequest(BaseModel):
    phone: str
    channel: str = "sms"


class OtpVerify(BaseModel):
    phone: str
    code: str


def _phone(raw: str) -> str:
    phone = normalize_phone(raw)
    if phone is None:
        raise HTTPException(status_code=422, detail="phone_invalid")
    return phone


def _ms(moment: dt.datetime | None) -> int | None:
    return None if moment is None else int(moment.timestamp() * 1000)


@router.post("/request", status_code=202)
async def request_code(
    body: OtpRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    settings = get_settings()  # per request: a forbidden configuration serves nothing
    phone = _phone(body.phone)
    now = dt.datetime.now(dt.UTC)
    latest = await _latest(session, phone)
    channel = body.channel if body.channel in ("sms", "whatsapp") else "sms"
    if latest is not None and latest.locked_until is not None and latest.locked_until > now:
        return {"status": "accepted"}  # locked: same answer, nothing sent, lock kept
    code = TEST_CODE if settings.enable_test_otp else new_code()
    session.add(
        OtpChallenge(
            id=uuid.uuid4(), phone_e164=phone, code_hash=hash_code(code, settings.otp_pepper),
            channel=channel, expires_at=now + OTP_TTL,
        )
    )
    await session.commit()
    sender.send(phone, code, channel)
    return {"status": "accepted"}


async def _latest(session: AsyncSession, phone: str) -> OtpChallenge | None:
    return (
        await session.execute(
            select(OtpChallenge)
            .where(OtpChallenge.phone_e164 == phone, OtpChallenge.consumed_at.is_(None))
            .order_by(OtpChallenge.last_sent_at.desc(), OtpChallenge.expires_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("/verify")
async def verify_code(
    body: OtpVerify, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    settings = get_settings()
    phone = _phone(body.phone)
    now = dt.datetime.now(dt.UTC)
    challenge = await _latest(session, phone)
    if challenge is None:
        raise HTTPException(status_code=400, detail={"code": "otp_invalid", "attempts_left": 0})
    state: OtpState = {"failed_attempts": challenge.failed_attempts, "locked_until_ms": _ms(challenge.locked_until)}
    now_ms = int(now.timestamp() * 1000)
    if is_locked(state, now_ms):  # checked before any comparison, the right code included
        raise _locked(int(((state["locked_until_ms"] or now_ms) - now_ms) / 1000) + 1)
    if challenge.expires_at <= now:
        raise HTTPException(status_code=410, detail={"code": "otp_expired"})
    if not check_code(body.code, challenge.code_hash, settings.otp_pepper):
        new = register_failure(state, now_ms)
        challenge.failed_attempts = new["failed_attempts"]
        if new["locked_until_ms"] is not None:
            challenge.locked_until = dt.datetime.fromtimestamp(new["locked_until_ms"] / 1000, dt.UTC)
        await session.commit()
        if new["locked_until_ms"] is not None:
            raise _locked(OTP_LOCK_SECONDS)
        left = max(0, 3 - new["failed_attempts"])
        raise HTTPException(status_code=400, detail={"code": "otp_invalid", "attempts_left": left})
    challenge.consumed_at = now
    user = (await session.execute(select(User).where(User.phone_e164 == phone))).scalar_one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), phone_e164=phone, status="pending")
        session.add(user)
        await session.flush()
    farms = (
        await session.execute(
            select(FarmMember.farm_id, FarmMember.role).where(
                FarmMember.user_id == user.id, FarmMember.removed_at.is_(None)
            )
        )
    ).all()
    access, expires = issue_token(
        user.id, settings.jwt_secret, [str(f) for f, _ in farms], {str(f): r for f, r in farms}
    )
    refresh = secrets.token_urlsafe(32)
    session.add(
        RefreshToken(
            id=uuid.uuid4(), user_id=user.id, family_id=uuid.uuid4(),
            token_hash=hashlib.sha256(refresh.encode()).hexdigest(),
        )
    )
    await session.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": expires.isoformat(),
        "user": {"id": str(user.id), "phone": user.phone_e164, "status": user.status},
        "farms": [{"id": str(f), "role": r} for f, r in farms],
    }


def _locked(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=423, detail={"code": "otp_locked", "retry_after": retry_after}
    )

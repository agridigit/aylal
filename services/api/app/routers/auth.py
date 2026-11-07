"""Phone + one-time code authentication (contracts/auth-otp.md)."""
import datetime as dt
import hashlib
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update
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
RESEND_DELAY = dt.timedelta(seconds=60)
WINDOW = dt.timedelta(hours=1)
MAX_SENDS_PER_PHONE = 5  # per hour
MAX_SENDS_PER_IP = 50  # per hour


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


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429, detail={"code": "otp_rate_limited", "retry_after": retry_after},
        headers={"Retry-After": str(max(1, retry_after))},
    )


@router.post("/request", status_code=202)
async def request_code(
    body: OtpRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    settings = get_settings()  # per request: a forbidden configuration serves nothing
    phone = _phone(body.phone)
    ip = request.client.host if request.client else "unknown"
    now = dt.datetime.now(dt.UTC)
    channel = body.channel if body.channel in ("sms", "whatsapp") else "sms"
    # Serialise requests for one phone: the lock is held until commit.
    latest = await _latest(session, phone, lock=True)
    if latest is not None and latest.locked_until is not None and latest.locked_until > now:
        return {"status": "accepted"}  # locked: same answer, nothing sent, lock kept
    sent_at = (
        await session.execute(
            select(func.max(OtpChallenge.last_sent_at)).where(OtpChallenge.phone_e164 == phone)
        )
    ).scalar_one()
    if sent_at is not None and sent_at + RESEND_DELAY > now:
        raise _too_many(int((sent_at + RESEND_DELAY - now).total_seconds()) + 1)
    since = now - WINDOW
    per_phone = (
        await session.execute(
            select(func.count()).where(OtpChallenge.phone_e164 == phone, OtpChallenge.last_sent_at > since)
        )
    ).scalar_one()
    per_ip = (
        await session.execute(
            select(func.count()).where(OtpChallenge.client_ip == ip, OtpChallenge.last_sent_at > since)
        )
    ).scalar_one()
    if per_phone >= MAX_SENDS_PER_PHONE or per_ip >= MAX_SENDS_PER_IP:
        raise _too_many(int(WINDOW.total_seconds()))
    inherited = latest is not None and latest.last_sent_at > since
    await session.execute(  # a new code invalidates the previous ones
        update(OtpChallenge)
        .where(OtpChallenge.phone_e164 == phone, OtpChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = TEST_CODE if settings.enable_test_otp else new_code()
    session.add(
        OtpChallenge(
            id=uuid.uuid4(), phone_e164=phone, code_hash=hash_code(code, settings.otp_pepper),
            channel=channel, expires_at=now + OTP_TTL, client_ip=ip,
            failed_attempts=latest.failed_attempts if inherited and latest else 0,
            locked_until=latest.locked_until if inherited and latest else None,
        )
    )
    await session.commit()
    sender.send(phone, code, channel)
    return {"status": "accepted"}


async def _latest(session: AsyncSession, phone: str, lock: bool = False) -> OtpChallenge | None:
    query = (
        select(OtpChallenge)
        .where(OtpChallenge.phone_e164 == phone, OtpChallenge.consumed_at.is_(None))
        .order_by(OtpChallenge.last_sent_at.desc(), OtpChallenge.expires_at.desc())
        .limit(1)
    )
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


@router.post("/verify")
async def verify_code(
    body: OtpVerify, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    settings = get_settings()
    phone = _phone(body.phone)
    now = dt.datetime.now(dt.UTC)
    challenge = await _latest(session, phone, lock=True)  # row lock: failures count atomically
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

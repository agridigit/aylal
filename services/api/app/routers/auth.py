"""Phone + one-time code authentication (contracts/auth-otp.md)."""
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, issue_token, sessions
from app.auth.client_ip import client_ip
from app.auth.otp import TEST_CODE, ConsoleSender, check_code, hash_code, new_code
from app.auth.tokens import ACCESS_TTL
from app.config import get_settings
from app.db.models import Farm, FarmMember, Invitation, OtpChallenge, RefreshToken, User
from app.db.session import get_session
from app.domain.otp_policy import (
    OTP_LOCK_SECONDS,
    OtpState,
    attempts_left,
    is_expired,
    is_locked,
    register_failure,
)
from app.domain.phone import normalize_phone
from app.domain.roles import INVITABLE_ROLES

router = APIRouter(prefix="/auth")
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
        raise HTTPException(status_code=422, detail={"code": "phone_invalid"})
    return phone


def _ms(moment: dt.datetime | None) -> int | None:
    return None if moment is None else int(moment.timestamp() * 1000)


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429, detail={"code": "otp_rate_limited", "retry_after": retry_after},
        headers={"Retry-After": str(max(1, retry_after))},
    )


@router.post("/otp/request", status_code=202)
async def request_code(
    body: OtpRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    settings = get_settings()  # per request: a forbidden configuration serves nothing
    phone = _phone(body.phone)
    ip = client_ip(request)
    now = dt.datetime.now(dt.UTC)
    channel = body.channel if body.channel in ("sms", "whatsapp") else "sms"
    # Serialise requests for one phone (also a phone with no row yet): held until commit.
    await _phone_lock(session, phone)
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
    per_ip = 0 if ip is None else (
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


async def _phone_lock(session: AsyncSession, phone: str) -> None:
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:p))"), {"p": phone})


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


@router.post("/otp/verify")
async def verify_code(
    body: OtpVerify, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    settings = get_settings()
    phone = _phone(body.phone)
    now = dt.datetime.now(dt.UTC)
    await _phone_lock(session, phone)
    challenge = await _latest(session, phone, lock=True)  # row lock: failures count atomically
    if challenge is None:
        raise HTTPException(status_code=400, detail={"code": "otp_invalid", "attempts_left": 0})
    state: OtpState = {"failed_attempts": challenge.failed_attempts, "locked_until_ms": _ms(challenge.locked_until)}
    now_ms = int(now.timestamp() * 1000)
    if is_locked(state, now_ms):  # checked before any comparison, the right code included
        raise _locked(int(((state["locked_until_ms"] or now_ms) - now_ms) / 1000) + 1)
    if is_expired(_ms(challenge.expires_at) or 0, now_ms):
        raise HTTPException(status_code=410, detail={"code": "otp_expired"})
    if not check_code(body.code, challenge.code_hash, settings.otp_pepper):
        new = register_failure(state, now_ms)
        challenge.failed_attempts = new["failed_attempts"]
        if new["locked_until_ms"] is not None:
            challenge.locked_until = dt.datetime.fromtimestamp(new["locked_until_ms"] / 1000, dt.UTC)
        await session.commit()
        if new["locked_until_ms"] is not None:
            raise _locked(OTP_LOCK_SECONDS)
        left = attempts_left(new)
        raise HTTPException(status_code=400, detail={"code": "otp_invalid", "attempts_left": left})
    challenge.consumed_at = now
    user = (await session.execute(select(User).where(User.phone_e164 == phone))).scalar_one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), phone_e164=phone, status="pending")
        session.add(user)
        await session.flush()
    await _honor_invitations(session, user, now)
    family = uuid.uuid4()
    raw = sessions.new_token()
    session.add(
        RefreshToken(id=uuid.uuid4(), user_id=user.id, family_id=family, token_hash=sessions.hash_token(raw))
    )
    payload = await _session_payload(session, user, raw)
    await session.commit()
    return payload


async def _honor_invitations(session: AsyncSession, user: User, now: dt.datetime) -> None:
    """Single-use: each pending, unexpired invitation of the verified number is consumed once."""
    pending = (
        await session.execute(
            select(Invitation)
            .join(Farm, Farm.id == Invitation.farm_id)
            .where(
                Invitation.phone_e164 == user.phone_e164, Invitation.status == "pending",
                Invitation.expires_at > now, Farm.deleted_at.is_(None),
            )
            .with_for_update(of=Invitation)
        )
    ).scalars().all()
    for inv in pending:
        inv.status = "accepted"
        if inv.role not in INVITABLE_ROLES:  # owner is never granted through an invitation
            continue
        member = await session.get(FarmMember, (inv.farm_id, user.id))
        if member is None:
            session.add(FarmMember(farm_id=inv.farm_id, user_id=user.id, role=inv.role))
        elif member.removed_at is not None:
            member.removed_at, member.role = None, inv.role
    await session.flush()


async def _session_payload(session: AsyncSession, user: User, refresh: str) -> dict[str, Any]:
    farms = (
        await session.execute(
            select(FarmMember.farm_id, FarmMember.role).where(
                FarmMember.user_id == user.id, FarmMember.removed_at.is_(None)
            )
        )
    ).all()
    access, expires = issue_token(
        user.id, get_settings().jwt_secret, [str(f) for f, _ in farms], {str(f): r for f, r in farms},
        ttl=ACCESS_TTL,
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": expires.isoformat(),
        "user": {"id": str(user.id), "phone": user.phone_e164, "status": user.status},
        "farms": [{"id": str(f), "role": r} for f, r in farms],
    }


class RefreshBody(BaseModel):
    refresh_token: str


def _record(row: RefreshToken) -> sessions.TokenRecord:
    return sessions.TokenRecord(
        id=row.id, family_id=row.family_id, token_hash=row.token_hash,
        rotated_at=row.rotated_at, revoked_at=row.revoked_at,
    )


async def _by_token(session: AsyncSession, token: str) -> RefreshToken | None:
    return (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == sessions.hash_token(token)).with_for_update()
        )
    ).scalar_one_or_none()


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "refresh_refused"})


@router.post("/refresh")
async def refresh(body: RefreshBody, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    now = dt.datetime.now(dt.UTC)
    row = await _by_token(session, body.refresh_token)
    if row is None:
        raise _unauthorized()
    decision = sessions.evaluate(_record(row), now)
    if decision == "reuse":  # a spent token came back: the family is compromised
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
    if decision != "rotate":
        raise _unauthorized()
    user = (await session.execute(select(User).where(User.id == row.user_id))).scalar_one()
    old, new, raw = sessions.rotate(_record(row), now)
    row.rotated_at = old.rotated_at
    session.add(RefreshToken(id=new.id, user_id=row.user_id, family_id=new.family_id, token_hash=new.token_hash))
    payload = await _session_payload(session, user, raw)
    await session.commit()
    return payload


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshBody, user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    row = await _by_token(session, body.refresh_token)
    if row is not None and row.user_id == user_id:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=dt.datetime.now(dt.UTC))
        )
        await session.commit()
    return Response(status_code=204)


def _locked(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=423, detail={"code": "otp_locked", "retry_after": retry_after}
    )

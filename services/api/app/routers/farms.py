"""Farm, team, parcel assignment and invitation routes (contracts/openapi.yaml).

Every /farms/{farm_id}/... route goes through `require(action)` (farm_context): non-member -> 404
identical to an unknown farm, insufficient role -> 403. Child objects are always loaded with
farm_id in the WHERE clause.
"""
import datetime as dt
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.auth.farm_context import NOT_FOUND, FarmContext, farm_context, require
from app.db.models import Farm, FarmMember, Invitation, Parcel, User, WorkerParcel
from app.db.session import get_session
from app.domain.phone import normalize_phone
from app.domain.validation import validate

router = APIRouter(prefix="/farms")
INVITATION_TTL = dt.timedelta(days=30)


class FarmPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    area_ha: float | None = Field(default=None, ge=0)


class RolePatch(BaseModel):
    role: Literal["manager", "worker"]


class ParcelAssignment(BaseModel):
    parcel_ids: list[uuid.UUID] = Field(max_length=2000)


class InvitationCreate(BaseModel):
    phone: str
    role: Literal["manager", "worker"]


def _farm_json(farm: Farm, role: str) -> dict[str, Any]:
    return {
        "id": str(farm.id),
        "name": farm.name,
        "owner_id": str(farm.owner_id) if farm.owner_id else None,
        "commune_id": farm.commune_id,
        "area_ha": None if farm.area_ha is None else float(farm.area_ha),
        "role": role,
    }


async def _active_member(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID) -> FarmMember:
    member = (
        await session.execute(
            select(FarmMember).where(
                FarmMember.farm_id == farm_id,
                FarmMember.user_id == user_id,
                FarmMember.removed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise NOT_FOUND
    return member


@router.get("")
async def my_farms(
    user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(Farm, FarmMember.role)
        .join(FarmMember, FarmMember.farm_id == Farm.id)
        .where(
            FarmMember.user_id == user_id,
            FarmMember.removed_at.is_(None),
            Farm.deleted_at.is_(None),
        )
        .order_by(Farm.created_at)
    )
    return [_farm_json(f, r) for f, r in rows.all()]


@router.post("", status_code=201)
async def create_farm(
    body: dict[str, Any],
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    verdict = validate("farm", body)
    if not verdict["valid"]:
        raise HTTPException(status_code=422, detail=verdict["errors"])
    farm = await create_owned_farm(session, uuid.uuid4(), user_id, body)
    await session.commit()
    return _farm_json(farm, "owner")


async def create_owned_farm(
    session: AsyncSession, farm_id: uuid.UUID, owner_id: uuid.UUID, data: dict[str, Any]
) -> Farm:
    """Insert a farm and its owner membership (owner_id is always the caller, never the client)."""
    loc = data["location"]
    commune = (
        await session.execute(
            text(
                "SELECT id FROM geo_communes"
                " WHERE ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) LIMIT 1"
            ),
            {"lon": loc["lon"], "lat": loc["lat"]},
        )
    ).scalar_one_or_none()
    farm = Farm(
        id=farm_id,
        name=str(data["name"]).strip(),
        owner_id=owner_id,
        commune_id=commune,
        area_ha=data.get("area_ha"),
    )
    session.add(farm)
    await session.flush()
    await session.execute(
        text(
            "UPDATE farms SET location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) WHERE id = :id"
        ),
        {"lon": loc["lon"], "lat": loc["lat"], "id": farm_id},
    )
    session.add(FarmMember(farm_id=farm_id, user_id=owner_id, role="owner"))
    await session.flush()
    return farm


@router.get("/{farm_id}")
async def get_farm(ctx: FarmContext = Depends(farm_context)) -> dict[str, Any]:
    farm = await ctx.session.get(Farm, ctx.farm_id)
    if farm is None or farm.deleted_at is not None:
        raise NOT_FOUND
    return _farm_json(farm, ctx.role)


@router.patch("/{farm_id}")
async def patch_farm(body: FarmPatch, ctx: FarmContext = Depends(require("farm.update"))) -> dict[str, Any]:
    farm = await ctx.session.get(Farm, ctx.farm_id)
    if farm is None or farm.deleted_at is not None:
        raise NOT_FOUND
    if body.name is not None:
        farm.name = body.name.strip()
    if body.area_ha is not None:
        farm.area_ha = body.area_ha
    await ctx.session.commit()
    return _farm_json(farm, ctx.role)


@router.get("/{farm_id}/members")
async def list_members(ctx: FarmContext = Depends(farm_context)) -> list[dict[str, Any]]:
    rows = await ctx.session.execute(
        select(FarmMember, User.display_name)
        .outerjoin(User, User.id == FarmMember.user_id)
        .where(FarmMember.farm_id == ctx.farm_id, FarmMember.removed_at.is_(None))
        .order_by(FarmMember.added_at)
    )
    return [
        {"user_id": str(m.user_id), "role": m.role, "display_name": name} for m, name in rows.all()
    ]


@router.patch("/{farm_id}/members/{user_id}")
async def change_role(
    user_id: uuid.UUID, body: RolePatch, ctx: FarmContext = Depends(require("member.role_change"))
) -> dict[str, Any]:
    member = await _active_member(ctx.session, ctx.farm_id, user_id)
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="owner_immutable")
    member.role = body.role
    if body.role != "worker":
        await ctx.session.execute(
            delete(WorkerParcel).where(
                WorkerParcel.farm_id == ctx.farm_id, WorkerParcel.user_id == user_id
            )
        )
    await ctx.session.commit()
    return {"user_id": str(user_id), "role": body.role}


@router.delete("/{farm_id}/members/{user_id}", status_code=204)
async def remove_member(
    user_id: uuid.UUID, ctx: FarmContext = Depends(require("member.remove"))
) -> Response:
    member = await _active_member(ctx.session, ctx.farm_id, user_id)
    if member.role == "owner":
        raise HTTPException(status_code=403, detail="owner_not_removable")
    member.removed_at = func.now()
    await ctx.session.execute(
        delete(WorkerParcel).where(
            WorkerParcel.farm_id == ctx.farm_id, WorkerParcel.user_id == user_id
        )
    )
    await ctx.session.commit()
    return Response(status_code=204)


@router.put("/{farm_id}/members/{user_id}/parcels")
async def assign_parcels(
    user_id: uuid.UUID, body: ParcelAssignment, ctx: FarmContext = Depends(require("parcels.assign"))
) -> dict[str, Any]:
    member = await _active_member(ctx.session, ctx.farm_id, user_id)
    if member.role != "worker":
        raise HTTPException(status_code=422, detail="not_a_worker")
    wanted = set(body.parcel_ids)
    if wanted:
        found = (
            await ctx.session.execute(
                select(Parcel.id).where(Parcel.farm_id == ctx.farm_id, Parcel.id.in_(wanted))
            )
        ).scalars().all()
        if set(found) != wanted:
            raise NOT_FOUND  # a parcel of another farm is indistinguishable from an unknown one
    await ctx.session.execute(
        delete(WorkerParcel).where(
            WorkerParcel.farm_id == ctx.farm_id, WorkerParcel.user_id == user_id
        )
    )
    for parcel_id in sorted(wanted):
        ctx.session.add(WorkerParcel(farm_id=ctx.farm_id, user_id=user_id, parcel_id=parcel_id))
    await ctx.session.commit()
    return {"user_id": str(user_id), "parcel_ids": [str(p) for p in sorted(wanted)]}


def _invitation_json(inv: Invitation) -> dict[str, Any]:
    return {
        "id": str(inv.id),
        "phone": inv.phone_e164,
        "role": inv.role,
        "status": inv.status,
        "expires_at": inv.expires_at.isoformat(),
    }


@router.get("/{farm_id}/invitations")
async def list_invitations(ctx: FarmContext = Depends(require("farm.update"))) -> list[dict[str, Any]]:
    rows = await ctx.session.execute(
        select(Invitation).where(Invitation.farm_id == ctx.farm_id).order_by(Invitation.created_at)
    )
    return [_invitation_json(i) for i in rows.scalars().all()]


@router.post("/{farm_id}/invitations", status_code=201)
async def invite(
    body: InvitationCreate,
    response: Response,
    ctx: FarmContext = Depends(require("member.invite")),
) -> dict[str, Any]:
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=422, detail="phone_invalid")
    already = (
        await ctx.session.execute(
            select(FarmMember.user_id)
            .join(User, User.id == FarmMember.user_id)
            .where(
                FarmMember.farm_id == ctx.farm_id,
                FarmMember.removed_at.is_(None),
                User.phone_e164 == phone,
            )
        )
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="already_member")
    expires = dt.datetime.now(dt.UTC) + INVITATION_TTL
    pending = (
        await ctx.session.execute(
            select(Invitation).where(
                Invitation.farm_id == ctx.farm_id,
                Invitation.phone_e164 == phone,
                Invitation.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if pending is not None:  # re-inviting refreshes the pending invitation
        pending.role, pending.expires_at = body.role, expires
        inv, response.status_code = pending, 200
    else:
        inv = Invitation(
            id=uuid.uuid4(), farm_id=ctx.farm_id, phone_e164=phone, role=body.role,
            status="pending", invited_by=ctx.user_id, expires_at=expires,
        )
        ctx.session.add(inv)
    try:
        await ctx.session.commit()
    except IntegrityError:
        await ctx.session.rollback()
        raise HTTPException(status_code=409, detail="invitation_pending") from None
    await ctx.session.refresh(inv)
    return _invitation_json(inv)


@router.delete("/{farm_id}/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(
    invitation_id: uuid.UUID, ctx: FarmContext = Depends(require("member.invite"))
) -> Response:
    inv = (
        await ctx.session.execute(
            select(Invitation).where(
                Invitation.id == invitation_id, Invitation.farm_id == ctx.farm_id
            )
        )
    ).scalar_one_or_none()
    if inv is None:
        raise NOT_FOUND
    await ctx.session.execute(
        update(Invitation)
        .where(Invitation.id == invitation_id, Invitation.farm_id == ctx.farm_id)
        .values(status="cancelled")
    )
    await ctx.session.commit()
    return Response(status_code=204)

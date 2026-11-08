"""Morning irrigation reminders (never reads `irrigation_plans`: the advice is read in the app): one per active member and per irrigated parcel THEY can see.

Recipients are replayed from `farm_members.removed_at IS NULL` at every run; parcels come from the shared visible-parcels
predicate (an archived or unassigned parcel is never reminded). The payload goes through the worker view whitelist: it carries a
parcel and a date, never an analysis, a soil or a salinity datum. Without a push gateway the delivery is reported unavailable.
"""
import datetime as dt
import os
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from clock import instant, local_day, local_hour
from gateways import PushGateway
from irrigation_db import clock_for
from monitoring_db import dsn
from worker_view import WORKER_ADVICE_KEYS

REMINDER_HOUR = 6
_NS = uuid.UUID("5c1d6a4e-8f0b-4c53-9a5e-0f4a7e2b9d31")
_MEMBERS = (
    "SELECT m.user_id, m.role FROM farm_members m JOIN farms f ON f.id = m.farm_id"
    " WHERE m.farm_id = $1 AND m.removed_at IS NULL AND f.deleted_at IS NULL ORDER BY m.user_id"
)


def reminder_payload(farm: uuid.UUID, parcel: uuid.UUID, day: dt.date) -> dict[str, str]:
    """Only whitelisted worker-view keys (worker_view.WORKER_ADVICE_KEYS)."""
    payload = {"parcel_id": str(parcel), "for_date": day.isoformat()}
    assert set(payload) <= set(WORKER_ADVICE_KEYS)
    return payload


async def send_irrigation_reminders(ctx: dict[str, Any], farm_id: uuid.UUID | str | None = None, now: str | dt.datetime | None = None) -> dict[str, Any]:
    import asyncpg

    clock = clock_for(now, ctx.get("clock"))
    day = local_day(instant(clock))
    gateway = ctx.get("gateway") or PushGateway(
        url=os.environ.get("AYLAL_PUSH_URL", ""), allowed_hosts=[h for h in os.environ.get("AYLAL_EXTERNAL_ALLOWED_HOSTS", "").split(",") if h.strip()]
    )
    targets: list[dict[str, Any]] = []
    sent = 0
    conn = await asyncpg.connect(dsn())
    try:
        farms = [uuid.UUID(str(farm_id))] if farm_id else [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]
        for farm in farms:
            for member in await conn.fetch(_MEMBERS, farm):
                query, args = asyncpg_query(
                    f"SELECT q.id FROM parcels q WHERE q.id IN ({VISIBLE_PARCELS_SQL}) AND q.irrigation IS DISTINCT FROM 'rainfed' ORDER BY q.id",
                    scope_params(farm, member["user_id"], member["role"]),
                )
                parcels = [r["id"] for r in await conn.fetch(query, *args)]
                if not parcels:
                    continue
                targets.append({"user_id": str(member["user_id"]), "parcel_ids": [str(p) for p in parcels]})
                if not gateway.configured():
                    continue
                prefs = await conn.fetchrow("SELECT push_token FROM notification_prefs WHERE farm_id = $1 AND user_id = $2 AND alerts_enabled", farm, member["user_id"])
                if prefs is None or not prefs["push_token"]:
                    continue
                answer = gateway.send(device_token=prefs["push_token"], alert_id=str(uuid.uuid5(_NS, f"{farm}:{member['user_id']}:{day}")), locale="fr")
                if answer["availability"] == "ok":
                    sent += 1
                    await conn.execute(
                        "INSERT INTO irrigation_notification_log (farm_id, user_id, for_date, sent_at) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                        farm, member["user_id"], day, instant(clock),
                    )
    finally:
        await conn.close()
    delivery = {"availability": "ok", "sent": sent} if gateway.configured() else {"availability": "unavailable", "reason": "gateway_not_configured"}
    return {"targets": targets, "delivery": delivery}


async def morning_irrigation_reminders(ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron entry: runs only at 06:00 local (before the advice is read at 07:00)."""
    if local_hour(instant(clock_for(None, ctx.get("clock")))) != REMINDER_HOUR:
        return {"targets": [], "delivery": {"availability": "unavailable", "reason": "not_the_hour"}}
    return await send_irrigation_reminders(ctx)

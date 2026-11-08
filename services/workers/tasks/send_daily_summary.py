"""Daily summary: one structured row per recipient, limited to that recipient's scope (FR-016, FR-021).

Recipients and their parcels come from the shared visibility predicate: a worker never gets a parcel that is not assigned
to them, an archived parcel is nobody's. The text itself is composed on the device from i18n keys.
"""
import datetime as dt
import json
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from monitoring_db import dsn, param

MOROCCO = dt.timezone(dt.timedelta(hours=1))


async def send_daily_summary(ctx: dict[str, Any], now: dt.datetime | None = None) -> int:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    hour = now.astimezone(MOROCCO).hour
    default_hour = int(await _default_hour(dsn()))
    created = 0
    conn = await asyncpg.connect(dsn())
    try:
        for farm in [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]:
            for m in await conn.fetch(
                "SELECT m.user_id, m.role, COALESCE(n.summary_hour, $2) AS hour, COALESCE(u.language, 'fr') AS lang FROM farm_members m"
                " LEFT JOIN notification_prefs n ON n.farm_id = m.farm_id AND n.user_id = m.user_id"
                " LEFT JOIN users u ON u.id = m.user_id WHERE m.farm_id = $1 AND m.removed_at IS NULL", farm, default_hour,
            ):
                if m["hour"] != hour:
                    continue
                query, args = asyncpg_query(
                    f"SELECT ps.parcel_id, ps.color, ps.reason_key FROM parcel_status ps WHERE ps.farm_id = :farm AND ps.color IN ('red', 'orange')"
                    f" AND ps.parcel_id IN ({VISIBLE_PARCELS_SQL}) ORDER BY CASE ps.color WHEN 'red' THEN 0 ELSE 1 END, ps.rank",
                    scope_params(farm, m["user_id"], m["role"]),
                )
                items = [{"parcel_id": str(r["parcel_id"]), "color": r["color"], "reason_key": r["reason_key"]} for r in await conn.fetch(query, *args)]
                done = await conn.execute(
                    "INSERT INTO daily_summaries (id, farm_id, user_id, summary_date, locale, payload) VALUES ($1,$2,$3,$4,$5,$6::jsonb)"
                    " ON CONFLICT (user_id, farm_id, summary_date) DO NOTHING",
                    uuid.uuid4(), farm, m["user_id"], now.astimezone(MOROCCO).date(), m["lang"] if m["lang"] in ("ary", "ar", "fr") else "fr",
                    json.dumps({"items": items}),
                )
                created += int(done.split()[-1])
    finally:
        await conn.close()
    return created


async def _default_hour(url: str) -> int:
    import asyncpg

    conn = await asyncpg.connect(url)
    try:
        return int(await param(conn, "summary_hour", 7))
    finally:
        await conn.close()

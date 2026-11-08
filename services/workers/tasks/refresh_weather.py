"""Hourly weather refresh: one gateway call per 0.1 degree cell and per 3 hours, within a daily budget (G5).

The worker is the only caller of the weather gateway. Without a configured gateway nothing is invented: farms keep their
last dated forecast and are marked unavailable with a reason.
"""
import asyncio
import datetime as dt
import json
import os
from typing import Any

from gateways import ObservedWeatherGateway, WeatherGateway, acquire_cell_slot, acquire_daily_budget
from monitoring_db import dsn

DAILY_BUDGET = int(os.environ.get("AYLAL_WEATHER_DAILY_BUDGET", "2000") or "2000")


def _cell(lat: float, lon: float) -> tuple[str, float, float]:
    lat_r, lon_r = round(lat, 1) + 0.0, round(lon, 1) + 0.0
    return f"{lat_r}:{lon_r}", lat_r, lon_r


def _icon(day: dict[str, Any]) -> dict[str, Any]:
    """Gateway `code` becomes the `icon` the API serves."""
    out = {k: v for k, v in day.items() if k != "code"}
    out["icon"] = str(day.get("icon", day.get("code", "")))
    return out


async def refresh_weather(ctx: dict[str, Any], now: dt.datetime | None = None) -> dict[str, int]:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    gateway = ctx.get("gateway") or WeatherGateway(
        url=os.environ.get("AYLAL_WEATHER_URL", ""),
        allowed_hosts=[h for h in os.environ.get("AYLAL_EXTERNAL_ALLOWED_HOSTS", "").split(",") if h.strip()],
    )
    observed_gateway = ctx.get("observed_gateway") or ObservedWeatherGateway(
        url=os.environ.get("AYLAL_WEATHER_OBSERVED_URL", ""),
        allowed_hosts=[h for h in os.environ.get("AYLAL_EXTERNAL_ALLOWED_HOSTS", "").split(",") if h.strip()],
    )
    stats = {"cells": 0, "farms": 0}
    conn = await asyncpg.connect(dsn())
    try:
        farms = await conn.fetch("SELECT id, ST_Y(location) AS lat, ST_X(location) AS lon FROM farms WHERE deleted_at IS NULL")
        by_cell: dict[str, list[Any]] = {}
        for f in farms:
            if f["lat"] is None:
                await _store(conn, f["id"], None, None, "unavailable", "farm_not_located", [])
                continue
            by_cell.setdefault(_cell(f["lat"], f["lon"])[0], []).append(f)
        for cell_id, members in by_cell.items():
            _, lat_r, lon_r = _cell(members[0]["lat"], members[0]["lon"])
            result: dict[str, Any]
            if not gateway.configured():
                result = {"availability": "unavailable", "reason": "gateway_not_configured"}
            elif not await acquire_cell_slot(cell_id, now) or not await acquire_daily_budget("weather", DAILY_BUDGET, now.date()):
                continue  # slot already taken or budget spent: keep the last forecast
            else:
                result = await asyncio.to_thread(gateway.fetch, lat_r=lat_r, lon_r=lon_r)
            stats["cells"] += 1
            await _observed(conn, observed_gateway, cell_id, lat_r, lon_r, now)
            days = [_icon(d) for d in result.get("days", [])]
            if result["availability"] == "ok":
                await conn.execute(
                    "INSERT INTO weather_cells (cell_id, fetched_at, days, source) VALUES ($1, $2, $3::jsonb, 'gateway')"
                    " ON CONFLICT (cell_id) DO UPDATE SET fetched_at = $2, days = $3::jsonb",
                    cell_id, now, json.dumps(days),
                )
            for f in members:
                await _store(conn, f["id"], cell_id, now if days else None, result["availability"], result.get("reason"), days)
                stats["farms"] += 1
    finally:
        await conn.close()
    return stats


async def _store(conn: Any, farm_id: Any, cell_id: str | None, fetched_at: dt.datetime | None, availability: str, reason: str | None, days: list[Any]) -> None:
    """Upsert; an unavailable answer keeps the last forecast and its date."""
    await conn.execute(
        "INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, reason, days) VALUES ($1, $2, $3, $4, $5, $6::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET availability = $4, reason = $5,"
        " cell_id = COALESCE($2, farm_weather.cell_id), fetched_at = COALESCE($3, farm_weather.fetched_at),"
        " days = CASE WHEN $4 = 'ok' THEN $6::jsonb ELSE farm_weather.days END",
        farm_id, cell_id, fetched_at, availability, reason, json.dumps(days),
    )


OBSERVED_SLOT_SECONDS = 6 * 3600


async def _observed(conn: Any, gateway: Any, cell_id: str, lat_r: float, lon_r: float, now: dt.datetime) -> None:
    """F4: observed rain of the 7 past days for a cell (optional gateway, once per 6 hours). Without it nothing is written and the
    balance falls back to the last forecast with a lowered confidence."""
    if not gateway.configured() or not await acquire_cell_slot(f"obs:{cell_id}", now, OBSERVED_SLOT_SECONDS):
        return
    if not await acquire_daily_budget("weather_observed", DAILY_BUDGET, now.date()):
        return
    day = now.date()
    answer = await asyncio.to_thread(gateway.fetch, lat_r=lat_r, lon_r=lon_r, date_from=(day - dt.timedelta(days=7)).isoformat(), date_to=(day - dt.timedelta(days=1)).isoformat())
    if answer["availability"] != "ok":
        return
    for d in answer["days"]:
        await conn.execute(
            "INSERT INTO weather_observed (cell_id, day, rain_mm, fetched_at) VALUES ($1, $2, $3, $4)"
            " ON CONFLICT (cell_id, day) DO UPDATE SET rain_mm = $3, fetched_at = $4",
            cell_id, dt.date.fromisoformat(str(d["date"])), d["rain_mm"], now,
        )

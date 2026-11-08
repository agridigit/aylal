"""Daily water balance and advice of one parcel (G5/G7): ONE implementation shared by the API (SQLAlchemy adapter) and the
worker (asyncpg adapter; the worker image carries a flat copy of this file). Self-contained: pure domain modules and an
abstract `Db`. Time comes from the injected clock only. Every referential value comes from the database: a gap makes the
advice `unavailable` with a reason, never a default coefficient."""
import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Any, Protocol

try:
    from app.domain.advice_confidence import advice_confidence
    from app.domain.application_rate import application_rate
    from app.domain.clock import Clock, instant, is_before_local_hour, local_day
    from app.domain.effective_rain import effective_rain
    from app.domain.et0 import resolve_et0
    from app.domain.irrigation_advice import compute_advice, reference_gap
    from app.domain.irrigation_efficiency import resolve_efficiency
    from app.domain.irrigation_units import from_duration
    from app.domain.leaching import leaching_fraction
    from app.domain.water_balance import replay_balance
    from app.irrigation.weather_input import rain_for_day
    from app.irrigation.worker_view import worker_assumptions
except ImportError:  # worker image: flat copies of the same files
    from advice_confidence import advice_confidence  # type: ignore[no-redef,import-not-found,unused-ignore]
    from application_rate import application_rate  # type: ignore[no-redef,import-not-found,unused-ignore]
    from clock import Clock, instant, is_before_local_hour, local_day  # type: ignore[no-redef,import-not-found,unused-ignore]
    from effective_rain import effective_rain  # type: ignore[no-redef,import-not-found,unused-ignore]
    from et0 import resolve_et0  # type: ignore[no-redef,import-not-found,unused-ignore]
    from irrigation_advice import compute_advice, reference_gap  # type: ignore[no-redef,import-not-found,unused-ignore]
    from irrigation_efficiency import resolve_efficiency  # type: ignore[no-redef,import-not-found,unused-ignore]
    from irrigation_units import from_duration  # type: ignore[no-redef,import-not-found,unused-ignore]
    from leaching import leaching_fraction  # type: ignore[no-redef,import-not-found,unused-ignore]
    from water_balance import replay_balance  # type: ignore[no-redef,import-not-found,unused-ignore]
    from weather_input import rain_for_day  # type: ignore[no-redef,import-not-found,unused-ignore]
    from worker_view import worker_assumptions  # type: ignore[no-redef,import-not-found,unused-ignore]

READY_HOUR = 7
LOOKBACK_DAYS = 7
MAX_WINDOW_DAYS = 399
STALE_AFTER = dt.timedelta(hours=24)
GATEWAY_REASONS = ("gateway_not_configured", "gateway_unreachable", "stale")
ASSUMED_MARK = "initial_state_assumed"


class Db(Protocol):
    async def fetch(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def execute(self, sql: str, params: dict[str, Any]) -> None: ...


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


def _n(v: float | None) -> Decimal | None:
    return None if v is None else Decimal(repr(round(float(v), 4)))


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


_PARCEL = (
    "SELECT p.id, p.irrigation, p.greenhouse, p.soil, COALESCE(p.area_calc_ha, p.area_declared_ha, ST_Area(p.geometry::geography) / 10000.0) AS area_ha, ST_Y(f.location) AS lat"
    " FROM parcels p JOIN farms f ON f.id = p.farm_id WHERE p.farm_id = :farm AND p.id = :parcel AND p.archived_at IS NULL AND f.deleted_at IS NULL"
)
_SEASON = (
    "SELECT s.id, s.started_at, COALESCE(s.stage_corrected, s.stage_estimated) AS stage, c.slug FROM seasons s JOIN crops c ON c.id = s.crop_id"
    " WHERE s.farm_id = :farm AND s.field_id = :parcel AND s.ended_at IS NULL ORDER BY s.started_at DESC LIMIT 1"
)
_SYSTEM = (
    "SELECT kind, emitter_flow_lph, emitter_spacing_m, row_spacing_m, pump_flow_m3h, sectors_count, efficiency"
    " FROM irrigation_systems WHERE farm_id = :farm AND parcel_id = :parcel AND parcel_archived_at IS NULL"
)
_CROP = (
    "SELECT kc, root_depth_m, depletion_fraction, ece_threshold_ds_m, ece_max_ds_m, validated FROM crop_irrigation_params"
    " WHERE crop_slug = :slug AND stage_key = :stage"
)
_SOILS = "SELECT texture_key, available_water_mm_per_m FROM soil_textures"
_PARAMS = "SELECT key, value FROM irrigation_params /* global referential: no farm_id */"
_WEATHER = "SELECT cell_id, fetched_at, availability, reason, days FROM farm_weather WHERE farm_id = :farm"
_OBSERVED = "SELECT day, rain_mm FROM weather_observed WHERE cell_id = :cell AND day >= :first AND day <= :last"
_APPLIED = (
    "SELECT performed_on AS day, sum(net_mm) AS net FROM irrigation_applied WHERE farm_id = :farm AND parcel_id = :parcel"
    " AND parcel_archived_at IS NULL AND performed_on >= :first AND performed_on <= :last GROUP BY performed_on"
)
_MOISTURE = (
    "SELECT measured_on AS day, depletion_mm FROM moisture_corrections WHERE farm_id = :farm AND parcel_id = :parcel"
    " AND parcel_archived_at IS NULL AND measured_on >= :first AND measured_on <= :last ORDER BY received_at"
)
_LAST_DAY = (
    "SELECT day FROM water_balance_days WHERE farm_id = :farm AND parcel_id = :parcel AND parcel_archived_at IS NULL AND day < :today"
    " ORDER BY day DESC LIMIT 1"
)
_BASE = (
    "SELECT depletion_mm FROM water_balance_days WHERE farm_id = :farm AND parcel_id = :parcel AND parcel_archived_at IS NULL AND day = :day"
)
_ASSUMED = (
    "SELECT 1 FROM water_balance_days WHERE farm_id = :farm AND parcel_id = :parcel AND parcel_archived_at IS NULL AND day < :today"
    " AND inputs_hash = 'initial_state_assumed' AND season_id IS NOT DISTINCT FROM :season LIMIT 1"
)
_ANALYSIS = (
    "SELECT water_source, ec_ds_m, analysed_on FROM water_analyses WHERE farm_id = :farm AND parcel_id = :parcel"
    " AND parcel_archived_at IS NULL AND status = 'active' ORDER BY analysed_on DESC LIMIT 1"
)
_VALID_PLAN = (
    "SELECT 1 FROM irrigation_plans WHERE farm_id = :farm AND parcel_id = :parcel AND parcel_archived_at IS NULL AND for_date <= :today"
    " AND kind <> 'unavailable' LIMIT 1"
)
_UPSERT_DAY = (
    "INSERT INTO water_balance_days (id, farm_id, parcel_id, season_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source,"
    " rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm, moisture_source, inputs_hash)"
    " VALUES (:id, :farm, :parcel, :season, :day, :et0, :method, :kc, :etc, :rain, :source, :eff, :irr, :taw, :raw, :dep, :moist, :hash)"
    " ON CONFLICT (parcel_id, day) DO UPDATE SET season_id = EXCLUDED.season_id, et0_mm = EXCLUDED.et0_mm, et0_method = EXCLUDED.et0_method,"
    " kc = EXCLUDED.kc, etc_mm = EXCLUDED.etc_mm, rain_mm = EXCLUDED.rain_mm, rain_source = EXCLUDED.rain_source,"
    " rain_eff_mm = EXCLUDED.rain_eff_mm, irrigation_net_mm = EXCLUDED.irrigation_net_mm, taw_mm = EXCLUDED.taw_mm, raw_mm = EXCLUDED.raw_mm,"
    " depletion_mm = EXCLUDED.depletion_mm, moisture_source = EXCLUDED.moisture_source, inputs_hash = EXCLUDED.inputs_hash"
)
_UPSERT_PLAN = (
    "INSERT INTO irrigation_plans (id, farm_id, parcel_id, season_id, for_date, kind, total_minutes, sectors, net_need_mm, leaching_fraction,"
    " stress_level, confidence, assumptions, worker_assumptions, unavailable_reason, computed_at, ready_before_7)"
    " VALUES (:id, :farm, :parcel, :season, :day, :kind, :minutes, CAST(:sectors AS jsonb), :net, :leach, :stress, :conf,"
    " CAST(:assumptions AS jsonb), CAST(:wassumptions AS jsonb), :reason, :at, :ready)"
    " ON CONFLICT (parcel_id, for_date) DO UPDATE SET season_id = EXCLUDED.season_id, kind = EXCLUDED.kind,"
    " total_minutes = EXCLUDED.total_minutes, sectors = EXCLUDED.sectors, net_need_mm = EXCLUDED.net_need_mm,"
    " leaching_fraction = EXCLUDED.leaching_fraction, stress_level = EXCLUDED.stress_level, confidence = EXCLUDED.confidence,"
    " assumptions = EXCLUDED.assumptions, worker_assumptions = EXCLUDED.worker_assumptions,"
    " unavailable_reason = EXCLUDED.unavailable_reason, computed_at = EXCLUDED.computed_at, ready_before_7 = EXCLUDED.ready_before_7"
)


async def _one(db: Db, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    rows = await db.fetch(sql, params)
    return rows[0] if rows else None


_PLAN_NOW = (
    "SELECT kind, total_minutes, net_need_mm, leaching_fraction, stress_level, unavailable_reason, confidence FROM irrigation_plans WHERE farm_id = :farm AND parcel_id = :parcel AND for_date = :day"
)


def _same_plan(old: dict[str, Any], out: dict[str, Any]) -> bool:
    numbers = all(_n(_f(old[k])) == _n(_f(out[o])) for k, o in (("net_need_mm", "net_need_mm"), ("leaching_fraction", "leaching_fraction")))
    return numbers and all(old[k] == out[o] for k, o in (
        ("kind", "kind"), ("total_minutes", "total_minutes"), ("stress_level", "stress_level"), ("unavailable_reason", "unavailable_reason"), ("confidence", "confidence")))


def _unavailable(day: dt.date, reason: str, at: dt.datetime, ready: bool) -> dict[str, Any]:
    return {
        "kind": "unavailable", "unavailable_reason": reason, "total_minutes": None, "net_need_mm": None, "sectors": [],
        "stress_level": None, "confidence": "low", "assumptions": [], "leaching_fraction": None,
        "for_date": day.isoformat(), "computed_at": at, "ready_before_7": ready,
    }


async def _store_plan(db: Db, farm: uuid.UUID, parcel: uuid.UUID, season: uuid.UUID | None, day: dt.date, out: dict[str, Any]) -> None:
    """The full assumptions and the worker view are written together (same statement, same transaction).
    `out["plan_changed"]` tells whether the advice differs from the one already stored for the day (a new plan counts as changed)."""
    old = await _one(db, _PLAN_NOW, {"farm": farm, "parcel": parcel, "day": day})
    out["plan_changed"] = old is None or not _same_plan(old, out)
    await db.execute(_UPSERT_PLAN, {
        "id": uuid.uuid4(), "farm": farm, "parcel": parcel, "season": season, "day": day, "kind": out["kind"],
        "minutes": out["total_minutes"], "sectors": json.dumps(out["sectors"]), "net": _n(out["net_need_mm"]),
        "leach": _n(out["leaching_fraction"]), "stress": out["stress_level"], "conf": out["confidence"],
        "assumptions": json.dumps(out["assumptions"], default=str),
        "wassumptions": json.dumps(worker_assumptions({"assumptions": out["assumptions"]})["assumptions"], default=str),
        "reason": out["unavailable_reason"], "at": out["computed_at"], "ready": out["ready_before_7"],
    })


async def compute_parcel_plan(db: Db, farm_id: uuid.UUID, parcel_id: uuid.UUID, clock: Clock, from_date: dt.date | None = None) -> dict[str, Any] | None:
    """Replay the balance up to the local day of `clock`, write the journal and the plan of the day. None for an invisible parcel."""
    now = instant(clock)
    today = local_day(now)
    ready = is_before_local_hour(now, READY_HOUR)
    key = {"farm": farm_id, "parcel": parcel_id}
    parcel = await _one(db, _PARCEL, key)
    if parcel is None:
        return None  # archived, deleted or unknown: nothing is computed and nothing is notified
    season = await _one(db, _SEASON, key)
    season_id = season["id"] if season else None

    async def finish_unavailable(reason: str, *, only_without_valid: bool = False) -> dict[str, Any]:
        out = _unavailable(today, reason, now, ready)
        if only_without_valid and await _one(db, _VALID_PLAN, {**key, "today": today}):
            return out  # an older valid advice stays the last known one: it is never overwritten
        await _store_plan(db, farm_id, parcel_id, season_id, today, out)
        return out

    weather = await _one(db, _WEATHER, {"farm": farm_id})
    days = _json(weather["days"]) if weather and weather["days"] is not None else []
    by_date = {d["date"]: d for d in days if isinstance(d, dict) and "date" in d}
    entry_today = by_date.get(today.isoformat())
    if weather is None or entry_today is None:
        reason = weather["reason"] if weather and weather["reason"] in GATEWAY_REASONS else "no_weather"
        return await finish_unavailable(reason, only_without_valid=True)

    crop = await _one(db, _CROP, {"slug": season["slug"], "stage": season["stage"] or ""}) if season else None
    soils = await db.fetch(_SOILS, {})
    gap = reference_gap({
        "crop_row": None if crop is None else {k: _f(crop[k]) if k != "validated" else bool(crop[k]) for k in ("kc", "root_depth_m", "depletion_fraction", "validated")},
        "soil_rows": [{"texture_key": r["texture_key"], "available_water_mm_per_m": _f(r["available_water_mm_per_m"])} for r in soils],
        "texture": parcel["soil"],
    })
    if gap["unavailable_reason"]:
        return await finish_unavailable(gap["unavailable_reason"])
    assert crop is not None
    params = {r["key"]: _json(r["value"]) for r in await db.fetch(_PARAMS, {})}
    greenhouse = bool(parcel["greenhouse"])
    method = params.get("effective_rain")
    if method is None and not greenhouse:
        return await finish_unavailable("no_effective_rain_method")

    kc = float(crop["kc"])
    taw = gap["soil_reserve_mm_per_m"] * float(crop["root_depth_m"])
    raw = float(crop["depletion_fraction"]) * taw
    area_m2 = None if parcel["area_ha"] is None else float(parcel["area_ha"]) * 10000
    lat = None if parcel["lat"] is None else round(float(parcel["lat"]), 1)

    # ---- window to replay: from the oldest changed day (or the day after the last stored one), at least yesterday ----
    yesterday = today - dt.timedelta(days=1)
    last = await _one(db, _LAST_DAY, {**key, "today": today})
    started = season["started_at"] if season else today
    start = from_date or (last["day"] + dt.timedelta(days=1) if last else max(started, today - dt.timedelta(days=LOOKBACK_DAYS)))
    start = max(min(start, yesterday), started, today - dt.timedelta(days=MAX_WINDOW_DAYS))
    start = min(start, today)
    base = await _one(db, _BASE, {**key, "day": start - dt.timedelta(days=1)})
    assumed = base is None or bool(await _one(db, _ASSUMED, {**key, "today": today, "season": season_id}))
    window = [start + dt.timedelta(days=i) for i in range((today - start).days + 1)]
    first, last_day = window[0], window[-1]
    observed = {r["day"]: float(r["rain_mm"]) for r in await db.fetch(_OBSERVED, {"cell": weather["cell_id"], "first": first, "last": last_day})}
    applied = {r["day"]: float(r["net"] or 0) for r in await db.fetch(_APPLIED, {**key, "first": first, "last": last_day})}
    measured = {r["day"]: float(r["depletion_mm"]) for r in await db.fetch(_MOISTURE, {**key, "first": first, "last": last_day})}
    nearest = by_date[min(by_date)]  # last known forecast, used for a past day the gateway no longer lists
    inputs: list[dict[str, Any]] = []
    meta: list[dict[str, Any]] = []
    for d in window:
        entry = by_date.get(d.isoformat()) or nearest
        rain = rain_for_day(day=d.isoformat(), observed=None if d not in observed else {"rain_mm": observed[d]}, last_forecast={"rain_mm": entry.get("rain_mm")})
        et0 = resolve_et0({
            "gateway_et0_mm": entry.get("et0_mm"), "tmin": entry.get("tmin"), "tmax": entry.get("tmax"),
            "lat": 0.0 if lat is None else lat, "doy": d.timetuple().tm_yday,
        })
        if rain["rain_mm"] is None or et0["et0_mm"] is None or (lat is None and et0["method"] == "hargreaves"):
            return await finish_unavailable("no_weather", only_without_valid=True)
        eff = effective_rain({"rain_mm": rain["rain_mm"], "method": method, "greenhouse": greenhouse})
        if eff["rain_eff_mm"] is None:
            return await finish_unavailable(eff.get("unavailable_reason") or "no_effective_rain_method")
        item = {"day": d.isoformat(), "et0_mm": et0["et0_mm"], "kc": kc, "rain_eff_mm": eff["rain_eff_mm"], "irrigation_net_mm": applied.get(d, 0.0)}
        if d in measured:
            item["moisture_depletion_mm"] = measured[d]
        inputs.append(item)
        meta.append({"et0_method": et0["method"], "rain_mm": rain["rain_mm"], "rain_source": eff.get("rain_source") or rain["rain_source"],
                     "measured": d in measured})
    replay = replay_balance({"taw_mm": taw, "initial_depletion_mm": 0.0 if base is None else float(base["depletion_mm"]), "days": inputs})
    rows = replay["days"] or []
    for i, (d, row) in enumerate(zip(window, rows, strict=True)):
        mark = ASSUMED_MARK if base is None and i == 0 else None
        await db.execute(_UPSERT_DAY, {
            "id": uuid.uuid4(), "farm": farm_id, "parcel": parcel_id, "season": season_id, "day": d, "et0": _n(inputs[i]["et0_mm"]),
            "method": meta[i]["et0_method"], "kc": _n(kc), "etc": _n(row["etc_mm"]), "rain": _n(meta[i]["rain_mm"]),
            "source": meta[i]["rain_source"], "eff": _n(inputs[i]["rain_eff_mm"]), "irr": _n(inputs[i]["irrigation_net_mm"]),
            "taw": _n(taw), "raw": _n(raw), "dep": _n(row["depletion_mm"]), "moist": "sensor" if meta[i]["measured"] else None, "hash": mark,
        })
    depletion = rows[-1]["depletion_mm"]

    # ---- the installation, salinity and the advice ----
    system_row = await _one(db, _SYSTEM, key)
    irrigated = parcel["irrigation"] != "rainfed"
    efficiency = {"efficiency": None, "is_default": False}
    rate = None
    system = None
    if system_row is not None:
        efficiency = resolve_efficiency({"kind": system_row["kind"], "efficiency": _f(system_row["efficiency"])})
        rate = application_rate({
            "kind": system_row["kind"], "emitter_flow_lph": _f(system_row["emitter_flow_lph"]), "emitter_spacing_m": _f(system_row["emitter_spacing_m"]),
            "row_spacing_m": _f(system_row["row_spacing_m"]), "pump_flow_m3h": _f(system_row["pump_flow_m3h"]),
            "sectors_count": system_row["sectors_count"], "area_m2": area_m2,
        })["rate_mm_h"]
        system = {"efficiency": efficiency["efficiency"], "rate_mm_h": rate, "sectors_count": system_row["sectors_count"]}
    analysis = await _one(db, _ANALYSIS, key)
    leaching = None
    if analysis is not None:
        leaching = leaching_fraction({
            "ecw_ds_m": float(analysis["ec_ds_m"]), "ece_threshold_ds_m": _f(crop["ece_threshold_ds_m"]), "ece_max_ds_m": _f(crop["ece_max_ds_m"]),
            "leaching_max": params.get("leaching_max"),
        })["leaching_fraction"]
    watch = params.get("stress_watch_ratio")
    advice = compute_advice({
        "irrigated": irrigated, "greenhouse": greenhouse, "has_system": system is not None, "system": system, "depletion_mm": depletion,
        "raw_mm": raw, "rain_mm_today": _f(entry_today.get("rain_mm")), "leaching_fraction": leaching, "stress_watch_ratio": watch,
    })
    sectors = []
    for s in advice["sectors"]:
        vol = from_duration({"minutes": s["minutes"], "rate_mm_h": rate, "area_m2": None if area_m2 is None else area_m2 / system_row["sectors_count"],
                             "efficiency": efficiency["efficiency"]})["volume_m3"] if system_row else None
        sectors.append({**s, "volume_m3": None if vol is None else round(vol, 3)})

    fetched = weather["fetched_at"]
    past = [m for m, d in zip(meta, window, strict=True) if d < today]
    rain_ref = past[-1]["rain_source"] if past else None
    analysis_age = None if analysis is None else (today - analysis["analysed_on"]).days
    old_limit = params.get("analysis_max_age_days")
    conf = advice_confidence({
        "validated": bool(gap.get("validated")), "et0_method": meta[-1]["et0_method"], "rain_source": rain_ref,
        "soil_default": bool(gap.get("soil_default")), "efficiency_is_default": bool(efficiency["is_default"]) and system is not None,
        "analysis_old": isinstance(old_limit, (int, float)) and analysis_age is not None and analysis_age > old_limit,
        "initial_state_assumed": assumed, "stale": fetched is None or now - fetched > STALE_AFTER,
    })
    eff_today = inputs[-1]["rain_eff_mm"]
    assumptions: list[dict[str, Any]] = [
        {"key": "et0", "value": round(inputs[-1]["et0_mm"], 2), "source": "gateway" if meta[-1]["et0_method"] == "gateway" else "computed"},
        {"key": "kc", "value": kc, "source": "referential", "validated": bool(gap.get("validated"))},
        {"key": "effective_rain", "value": round(eff_today, 2), "source": "computed"},
    ]
    if system is not None:
        assumptions.append({"key": "efficiency", "value": efficiency["efficiency"], "source": "default" if efficiency["is_default"] else "user"})
        if rate is not None:
            assumptions.append({"key": "application_rate", "value": round(rate, 2), "source": "computed"})
    if rain_ref is not None:
        assumptions.append({"key": "rain_source", "value": rain_ref, "source": "gateway"})
    assumptions += [
        {"key": "taw_mm", "value": round(taw, 1), "source": "computed"},
        {"key": "soil_texture", "value": gap["texture_used"], "source": "default" if gap.get("soil_default") else "referential"},
    ]
    if analysis is not None:
        assumptions += [
            {"key": "ece_ds_m", "value": float(analysis["ec_ds_m"]), "source": "user"},
            {"key": "water_source", "value": analysis["water_source"], "source": "user"},
            {"key": "analysis_age_days", "value": analysis_age, "source": "computed"},
        ]
        if leaching is not None:
            assumptions.append({"key": "leaching_fraction", "value": round(leaching, 4), "source": "computed"})
    if assumed:
        assumptions.append({"key": "initial_state", "value": "field_capacity", "source": "default"})
    out = {
        "kind": advice["kind"], "unavailable_reason": advice["unavailable_reason"], "total_minutes": advice["total_minutes"],
        "net_need_mm": advice["net_need_mm"], "sectors": sectors, "stress_level": advice["stress_level"], "confidence": conf["confidence"],
        "assumptions": assumptions, "leaching_fraction": leaching, "for_date": today.isoformat(), "computed_at": now, "ready_before_7": ready,
        "factors": conf["factors"],
    }
    await _store_plan(db, farm_id, parcel_id, season_id, today, out)
    return out

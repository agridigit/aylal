"""Irrigation advice and referential gaps, mirror of irrigation-advice.ts. Never a default agronomic value."""
from typing import Any

try:
    from app.domain.application_rate import irrigation_minutes
    from app.domain.leaching import gross_need
    from app.domain.rainfed_stress import stress_level
except ImportError:  # worker image: flat copies of the same files
    from application_rate import irrigation_minutes  # type: ignore[no-redef,import-not-found,unused-ignore]
    from leaching import gross_need  # type: ignore[no-redef,import-not-found,unused-ignore]
    from rainfed_stress import stress_level  # type: ignore[no-redef,import-not-found,unused-ignore]

POSTPONE_RAIN_MM = 10  # strictly above, on the local day (CPS section 9)


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _base(kind: str, reason: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "net_need_mm": None, "total_minutes": None, "sectors": [], "stress_level": None, "unavailable_reason": reason}


def compute_advice(i: dict[str, Any]) -> dict[str, Any]:
    raw = i.get("raw_mm")
    if not isinstance(raw, (int, float)):
        return _base("unavailable", "no_soil_reserve")
    if not i["irrigated"]:
        out = _base("rainfed_stress")
        out["stress_level"] = stress_level({"depletion_mm": i["depletion_mm"], "raw_mm": raw, "watch_ratio": i.get("stress_watch_ratio")})["stress_level"]
        return out
    system = i.get("system")
    if not i.get("has_system") or not system:
        return _base("unavailable", "no_system")
    if i["depletion_mm"] < raw:
        return _base("no_need")
    rain = i.get("rain_mm_today")
    if not i.get("greenhouse") and isinstance(rain, (int, float)) and rain > POSTPONE_RAIN_MM:
        return _base("postpone_rain")
    lr = i.get("leaching_fraction")
    gross = gross_need({"net_need_mm": i["depletion_mm"], "leaching_fraction": lr if _num(lr) else 0})["gross_need_mm"]
    m = irrigation_minutes({"net_need_mm": gross, "efficiency": system.get("efficiency"), "rate_mm_h": system.get("rate_mm_h")})["minutes"]
    if m is None:
        return _base("unavailable", "no_system")
    out = _base("irrigate")
    out["net_need_mm"] = gross
    out["total_minutes"] = m * system["sectors_count"]
    out["sectors"] = [{"sector_no": k + 1, "minutes": m} for k in range(system["sectors_count"])]
    return out


def reference_gap(i: dict[str, Any]) -> dict[str, Any]:
    c = i.get("crop_row")
    if not c or not _num(c.get("kc")):
        return {"unavailable_reason": "no_crop_coefficient"}
    if not _num(c.get("root_depth_m")):
        return {"unavailable_reason": "no_root_depth"}
    if not _num(c.get("depletion_fraction")):
        return {"unavailable_reason": "no_depletion_fraction"}
    rows = i["soil_rows"]
    if not rows:
        return {"unavailable_reason": "no_soil_reference"}
    tex = i.get("texture")
    match = next((r for r in rows if tex and r["texture_key"] == tex), None)
    if match is not None:
        if not _num(match.get("available_water_mm_per_m")):
            return {"unavailable_reason": "no_soil_reserve"}
        return {"unavailable_reason": None, "soil_reserve_mm_per_m": match["available_water_mm_per_m"], "texture_used": match["texture_key"], "soil_default": False, "validated": c["validated"]}
    with_reserve = [r for r in rows if _num(r.get("available_water_mm_per_m"))]
    if not with_reserve:
        return {"unavailable_reason": "no_soil_reserve"}
    weakest = min(with_reserve, key=lambda r: r["available_water_mm_per_m"])
    return {"unavailable_reason": None, "soil_reserve_mm_per_m": weakest["available_water_mm_per_m"], "texture_used": weakest["texture_key"], "soil_default": True, "validated": c["validated"]}

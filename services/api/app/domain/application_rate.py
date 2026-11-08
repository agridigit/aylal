"""Application rate (mm/h) and duration, mirror of application-rate.ts."""
from typing import Any


def _pos(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def application_rate(i: dict[str, Any]) -> dict[str, Any]:
    if _pos(i.get("emitter_flow_lph")) and _pos(i.get("emitter_spacing_m")) and _pos(i.get("row_spacing_m")):
        return {"rate_mm_h": i["emitter_flow_lph"] / (i["emitter_spacing_m"] * i["row_spacing_m"])}
    if _pos(i.get("pump_flow_m3h")) and _pos(i.get("area_m2")) and _pos(i.get("sectors_count")):
        return {"rate_mm_h": i["pump_flow_m3h"] * 1000 / (i["area_m2"] / i["sectors_count"])}
    return {"rate_mm_h": None}


def irrigation_minutes(i: dict[str, Any]) -> dict[str, Any]:
    if not _pos(i.get("rate_mm_h")) or not _pos(i.get("efficiency")):
        return {"minutes": None}
    return {"minutes": _round(i["net_need_mm"] / (i["efficiency"] * i["rate_mm_h"]) * 60)}


def _round(x: float) -> int:
    return int(x + 0.5)  # half up, like Math.round for positive values

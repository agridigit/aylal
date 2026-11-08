"""Rainfed stress indicator, mirror of rainfed-stress.ts."""
from typing import Any


def stress_level(i: dict[str, Any]) -> dict[str, Any]:
    raw, ratio = i.get("raw_mm"), i.get("watch_ratio")
    if not isinstance(raw, (int, float)):
        return {"stress_level": None, "unavailable_reason": "no_soil_reserve"}
    if i["depletion_mm"] >= raw:
        return {"stress_level": "high"}
    if isinstance(ratio, (int, float)) and i["depletion_mm"] >= ratio * raw:
        return {"stress_level": "watch"}
    return {"stress_level": "none"}

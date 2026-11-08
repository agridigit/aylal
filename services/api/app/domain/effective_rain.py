"""Effective rain from a referential method only, mirror of effective-rain.ts."""
from typing import Any


def effective_rain(i: dict[str, Any]) -> dict[str, Any]:
    if i.get("greenhouse"):
        return {"rain_eff_mm": 0, "rain_source": "ignored_greenhouse"}
    if not i["rain_mm"] >= 0:
        return {"rain_eff_mm": None, "unavailable_reason": "no_weather"}
    m = i.get("method")
    if m and m.get("method") == "fraction" and isinstance((m.get("params") or {}).get("fraction"), (int, float)):
        return {"rain_eff_mm": i["rain_mm"] * m["params"]["fraction"]}
    return {"rain_eff_mm": None, "unavailable_reason": "no_effective_rain_method"}

"""Daily water balance replay, mirror of water-balance.ts."""
from typing import Any


def replay_balance(i: dict[str, Any]) -> dict[str, Any]:
    taw = i.get("taw_mm")
    if not isinstance(taw, (int, float)):
        return {"days": None, "unavailable_reason": "no_soil_reserve"}
    d = i["initial_depletion_mm"]
    out = []
    for x in i["days"]:
        etc = x["et0_mm"] * x["kc"]
        m = x.get("moisture_depletion_mm")
        d = m if isinstance(m, (int, float)) else d + etc - x["rain_eff_mm"] - x["irrigation_net_mm"]
        d = min(taw, max(0, d))
        out.append({"day": x["day"], "etc_mm": etc, "depletion_mm": d})
    return {"days": out}

"""FAO-56 eq. 21 (Ra) and eq. 52 (Hargreaves-Samani), mirror of et0.ts."""
import math
from typing import Any

_GSC = 0.082


def extraterrestrial_radiation(i: dict[str, Any]) -> dict[str, Any]:
    phi = math.radians(i["lat"])
    doy = i["doy"]
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    ra = (24 * 60 / math.pi) * _GSC * dr * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    return {"ra_mj_m2_day": ra}


def hargreaves_et0(i: dict[str, Any]) -> dict[str, Any]:
    ra = extraterrestrial_radiation(i)["ra_mj_m2_day"]
    rng = max(0.0, i["tmax"] - i["tmin"])
    et0 = 0.0023 * ((i["tmax"] + i["tmin"]) / 2 + 17.8) * math.sqrt(rng) * ra * 0.408
    return {"et0_mm": max(0.0, et0)}


def resolve_et0(i: dict[str, Any]) -> dict[str, Any]:
    if isinstance(i.get("gateway_et0_mm"), (int, float)):
        return {"et0_mm": i["gateway_et0_mm"], "method": "gateway"}
    if isinstance(i.get("tmin"), (int, float)) and isinstance(i.get("tmax"), (int, float)):
        return {"et0_mm": hargreaves_et0(i)["et0_mm"], "method": "hargreaves"}
    return {"et0_mm": None, "method": None, "unavailable_reason": "no_weather"}

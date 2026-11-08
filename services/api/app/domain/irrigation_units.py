"""Duration <-> volume <-> net depth, mirror of irrigation-units.ts."""
from typing import Any

try:
    from app.domain.application_rate import _pos, _round
except ImportError:  # worker image: flat copy
    from application_rate import _pos, _round  # type: ignore[no-redef,import-not-found,unused-ignore]


def from_duration(i: dict[str, Any]) -> dict[str, Any]:
    if not _pos(i.get("rate_mm_h")) or not _pos(i.get("area_m2")):
        return {"volume_m3": None, "net_mm": None}
    gross = i["rate_mm_h"] * i["minutes"] / 60
    return {"volume_m3": gross * i["area_m2"] / 1000, "net_mm": gross * i["efficiency"] if _pos(i.get("efficiency")) else None}


def from_volume(i: dict[str, Any]) -> dict[str, Any]:
    if not _pos(i.get("area_m2")):
        return {"minutes": None, "net_mm": None}
    gross = i["volume_m3"] * 1000 / i["area_m2"]
    net = gross * i["efficiency"] if _pos(i.get("efficiency")) else None
    return {"minutes": _round(gross / i["rate_mm_h"] * 60) if _pos(i.get("rate_mm_h")) else None, "net_mm": net}

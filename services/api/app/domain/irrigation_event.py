"""R3: validation of an irrigation event, mirror of irrigation-event.ts."""
import datetime as dt
from typing import Any

from app.domain.irrigation_limits import LIMITS


def _err(field: str, code: str) -> dict[str, str]:
    return {"field": field, "code": code, "i18n_key": f"irrigation.event.{field}.{code}"}


def validate_irrigation_event(i: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    dur, vol = i.get("duration_min"), i.get("volume_m3")
    has_d, has_v = dur is not None, vol is not None
    if has_d == has_v:
        errors.append(_err("volume_m3" if has_d else "duration_min", "exactly_one_of_duration_or_volume"))
    if dur is not None and not 1 <= dur <= LIMITS["duration_min"]:
        errors.append(_err("duration_min", "out_of_range"))
    if vol is not None and not vol > 0:
        errors.append(_err("volume_m3", "out_of_range"))
    if vol is not None and i.get("area_ha") and vol > LIMITS["volume_m3_per_ha"] * i["area_ha"]:
        errors.append(_err("volume_m3", "out_of_range"))
    back = (dt.date.fromisoformat(i["today"]) - dt.date.fromisoformat(i["performed_on"])).days
    if back < 0:
        errors.append(_err("performed_on", "in_the_future"))
    elif back > LIMITS["backdate_days"]:
        errors.append(_err("performed_on", "too_old"))
    if i["slot_count"] >= LIMITS["events_per_day_sector"]:
        errors.append(_err("performed_on", "events_per_day_sector"))
    return {"valid": not errors, "errors": errors, "possible_duplicate": i["slot_count"] >= 1}

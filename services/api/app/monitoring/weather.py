"""Weather shaping for the API: today and the 7 next days, nothing padded, interpolated or defaulted (R1-A1)."""
import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

HORIZON_DAYS = 8
_VALUE_KEYS = ("tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct")
_ICONS = {0: "sun", 1: "sun", 2: "cloud_sun", 3: "cloud", 45: "fog", 48: "fog", 61: "rain", 63: "rain", 65: "rain",
          80: "rain", 81: "rain", 82: "rain", 95: "storm", 96: "storm", 99: "storm"}


def _icon(day: Mapping[str, Any]) -> str:
    icon = day.get("icon")
    if isinstance(icon, str) and icon:
        return icon
    code = day.get("icon_code")
    return _ICONS.get(code, "cloud") if code is not None else "unknown"


def today_plus_seven(days: Sequence[Mapping[str, Any]], today: dt.date) -> list[dict[str, Any]]:
    """Days from `today` to `today` + 7 in date order; a day missing a value is dropped, never filled."""
    last = today + dt.timedelta(days=HORIZON_DAYS - 1)
    kept: list[dict[str, Any]] = []
    for d in days:
        try:
            on = dt.date.fromisoformat(str(d["date"]))
        except (KeyError, ValueError):
            continue
        if not today <= on <= last or any(d.get(k) is None for k in _VALUE_KEYS):
            continue
        kept.append({"date": on.isoformat(), **{k: d[k] for k in _VALUE_KEYS}, "icon": _icon(d)})
    return sorted(kept, key=lambda d: d["date"])

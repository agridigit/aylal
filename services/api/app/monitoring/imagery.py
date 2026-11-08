"""Zonal statistics of a scene over a parcel and the initial history window (R3-A1, R3-A2)."""
import datetime as dt
from typing import Any

import numpy as np

# Sentinel-2 scene classification: 4 vegetation, 5 bare soil, 6 water, 7 low-probability cloud are clear enough.
SCL_CLEAR = (4, 5, 6, 7)


def backfill_window(today: dt.date) -> tuple[dt.date, dt.date]:
    """The last 12 months, ending today."""
    try:
        start = today.replace(year=today.year - 1)
    except ValueError:  # 29 February
        start = today.replace(year=today.year - 1, day=28)
    return start, today


def _index(a: Any, b: Any) -> Any:
    denom = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denom != 0, (a - b) / denom, np.nan)


def zonal_stats(*, b04: Any, b08: Any, b11: Any, scl: Any, mask: Any) -> dict[str, Any]:
    """Means over the clear pixels of the parcel only; `clear_pct` is the clear share of the parcel pixels."""
    inside = np.asarray(mask, dtype=bool)
    total = int(inside.sum())
    clear = inside & np.isin(scl, SCL_CLEAR)
    n_clear = int(clear.sum())
    if total == 0 or n_clear == 0:
        return {"vigor_mean": None, "plant_moisture_mean": None, "clear_pct": 0.0}
    vigor = _index(b08[clear], b04[clear])
    moisture = _index(b08[clear], b11[clear])

    def mean(a: Any) -> float | None:
        good = a[np.isfinite(a)]
        return float(good.mean()) if good.size else None

    return {"vigor_mean": mean(vigor), "plant_moisture_mean": mean(moisture), "clear_pct": 100.0 * n_clear / total}

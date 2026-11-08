"""Weather alert rules, mirror of packages/domain/src/alert-rules.ts (shared vectors f3_alert_rules.json)."""
import hashlib
from collections.abc import Mapping
from typing import Any

FROST_CRITICAL_MARGIN_C = 1  # frost this far under the threshold is critical, closer is a warning
RAIN_CRITICAL_RATIO = 1.5  # rain at this multiple of the threshold is critical


def evaluate_day(t: Mapping[str, Any] | None, day: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Alerts of one forecast day for one crop and stage. Without thresholds nothing is produced."""
    if t is None:
        return []
    out: list[dict[str, Any]] = []
    if t["frost_c"] is not None and day["tmin"] <= t["frost_c"]:
        margin = t["frost_c"] - day["tmin"]
        out.append({
            "type": "frost", "severity": "critical" if margin >= FROST_CRITICAL_MARGIN_C else "warning",
            "reason_key": "alert.frost", "advice_key": None, "params": {"tmin": day["tmin"], "threshold": t["frost_c"]},
        })
    if day["tmax"] >= t["chergui_tmax_c"] and day["humidity_pct"] <= t["chergui_rh_max_pct"] and day["wind_kmh"] >= t["chergui_wind_kmh"]:
        out.append({
            "type": "chergui", "severity": "warning", "reason_key": "alert.chergui", "advice_key": None,
            "params": {"tmax": day["tmax"], "humidity_pct": day["humidity_pct"], "wind_kmh": day["wind_kmh"]},
        })
    if day["rain_mm"] >= t["heavy_rain_mm_24h"]:
        severity = "critical" if day["rain_mm"] >= t["heavy_rain_mm_24h"] * RAIN_CRITICAL_RATIO else "warning"
        out.append({
            "type": "heavy_rain", "severity": severity, "reason_key": "alert.heavy_rain", "advice_key": None,
            "params": {"rain_mm": day["rain_mm"], "threshold": t["heavy_rain_mm_24h"]},
        })
    if day["wind_kmh"] > t["strong_wind_kmh"]:
        out.append({
            "type": "strong_wind", "severity": "warning", "reason_key": "alert.strong_wind", "advice_key": "do_not_spray",
            "params": {"wind_kmh": day["wind_kmh"], "threshold": t["strong_wind_kmh"]},
        })
    return out


def dedup_key(*, farm_id: str, parcel_id: str, crop_slug: str, type: str, forecast_day: str) -> str:
    """One alert per (farm, parcel, crop, type, forecast day): sha-256 hex of the components."""
    return hashlib.sha256(f"{farm_id}|{parcel_id}|{crop_slug}|{type}|{forecast_day}".encode()).hexdigest()

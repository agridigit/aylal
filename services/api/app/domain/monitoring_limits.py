"""F3 caps (G4), mirror of packages/domain/src/monitoring-limits.ts (shared vectors f3_limits.json)."""

LIMITS: dict[str, int] = {
    "page_default": 50,
    "page_max": 100,
    "series_months": 24,
    "series_points": 400,
    "compare_points": 200,
    "weather_horizon_days": 8,
    "alerts_per_farm": 1000,
    "alerts_per_parcel": 20,
    "zones_per_parcel": 5,
    "zones_per_farm": 200,
    "polygon_vertices": 200,
    "note_chars": 500,
    "photo_bytes": 3 * 1024 * 1024,
    "observations_per_zone": 20,
    "observations_per_farm_year": 2000,
    "sync_batch": 100,
    "reprocess_per_parcel_day": 3,
    "imagery_jobs_per_farm": 5,
    "raster_bytes": 500 * 1024 * 1024,
    "init_window_months": 12,
    "body_bytes": 64 * 1024,
}

_MAX_COUNT = frozenset({
    "series_months", "series_points", "compare_points", "alerts_per_farm", "alerts_per_parcel", "zones_per_parcel",
    "zones_per_farm", "polygon_vertices", "note_chars", "photo_bytes", "observations_per_zone",
    "observations_per_farm_year", "sync_batch", "reprocess_per_parcel_day", "imagery_jobs_per_farm", "raster_bytes",
    "init_window_months",
})


def within_limit(rule: str, value: float) -> bool:
    """True when `value` respects the cap named `rule`; an unknown rule is refused."""
    if isinstance(value, bool):
        return False
    if rule == "limit":
        return 1 <= value <= LIMITS["page_max"]
    if rule == "weather_horizon_days":
        return value == LIMITS["weather_horizon_days"]
    return rule in _MAX_COUNT and 0 <= value <= LIMITS[rule]

"""F4 caps (G4), mirror of packages/domain/src/irrigation-limits.ts (shared vectors f4_limits.json)."""

LIMITS: dict[str, int] = {
    "page_default": 50,
    "page_max": 100,
    "sync_batch": 100,
    "window_months": 24,
    "points": 400,
    "jobs_per_farm": 5,
    "sectors": 50,
    "system_versions": 50,
    "events_per_day_sector": 24,
    "duration_min": 1440,
    "volume_m3_per_ha": 1000,
    "backdate_days": 400,
    "water_analyses": 50,
    "ec_ds_m": 100,
}

_RANGES: dict[str, tuple[float, float]] = {
    "sectors": (1, LIMITS["sectors"]),
    "system_versions": (0, LIMITS["system_versions"]),
    "events_per_day_sector": (0, LIMITS["events_per_day_sector"]),
    "duration_min": (1, LIMITS["duration_min"]),
    "volume_m3_per_ha": (0, LIMITS["volume_m3_per_ha"]),
    "backdate_days": (0, LIMITS["backdate_days"]),
    "water_analyses": (0, LIMITS["water_analyses"]),
    "sync_batch": (0, LIMITS["sync_batch"]),
    "limit": (1, LIMITS["page_max"]),
    "window_months": (0, LIMITS["window_months"]),
    "points": (0, LIMITS["points"]),
    "jobs_per_farm": (0, LIMITS["jobs_per_farm"]),
}


def within_limit(rule: str, value: float) -> bool:
    """True when `value` respects the cap named `rule`; an unknown rule is refused."""
    if isinstance(value, bool):
        return False
    if rule == "ec_ds_m":
        return 0 < value <= LIMITS["ec_ds_m"]
    if rule not in _RANGES:
        return False
    lo, hi = _RANGES[rule]
    return lo <= value <= hi

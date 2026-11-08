"""A scene is published only when at least 80 % of the parcel is clear (FR-007); never more than 100 %."""
CLOUD_MIN_CLEAR_PCT = 80.0


def is_scene_publishable(clear_pct: float, min_clear_pct: float = CLOUD_MIN_CLEAR_PCT) -> bool:
    return min_clear_pct <= clear_pct <= 100

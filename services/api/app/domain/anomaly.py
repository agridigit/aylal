"""Vigor anomaly rules, mirror of packages/domain/src/anomaly.ts."""
from collections.abc import Sequence


def is_anomalous_zone(drop_score: float, pixels: int, anomaly_drop: float, anomaly_min_pixels: int) -> bool:
    return drop_score >= anomaly_drop and pixels >= anomaly_min_pixels


def is_resolved(recent_vigor: Sequence[float], threshold: float) -> bool:
    """Resolved when the two most recent valid scenes are above the threshold."""
    return len(recent_vigor) >= 2 and all(v > threshold for v in recent_vigor[-2:])

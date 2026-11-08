"""Imagery is low reliability on a small parcel or under a greenhouse (FR-009)."""


def imagery_reliability(area_ha: float, greenhouse: bool, min_area_ha: float) -> str:
    return "low" if greenhouse or area_ha < min_area_ha else "ok"

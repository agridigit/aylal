"""Pure point-in-commune lookup (R4-A2). Coordinates are (lon, lat); the boundary counts as inside."""
from collections.abc import Sequence
from typing import Any

Point = tuple[float, float]
Ring = Sequence[Point]


def _on_segment(px: float, py: float, a: Point, b: Point) -> bool:
    cross = (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])
    if cross != 0:
        return False
    return min(a[0], b[0]) <= px <= max(a[0], b[0]) and min(a[1], b[1]) <= py <= max(a[1], b[1])


def _ring_position(px: float, py: float, ring: Ring) -> str:
    """Return 'boundary', 'inside' or 'outside' (ray casting)."""
    inside = False
    for a, b in zip(ring, ring[1:], strict=False):
        if _on_segment(px, py, a, b):
            return "boundary"
        if (a[1] > py) != (b[1] > py):
            x_cross = a[0] + (py - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if px < x_cross:
                inside = not inside
    return "inside" if inside else "outside"


def _rings(polygon: Any) -> Sequence[Ring]:
    """A polygon entry is either a bare ring or a list of rings (outer first, then holes)."""
    return [polygon] if isinstance(polygon[0][0], int | float) else list(polygon)


def _contains(px: float, py: float, polygon: Any) -> bool:
    outer, *holes = _rings(polygon)
    if _ring_position(px, py, outer) == "outside":
        return False
    return all(_ring_position(px, py, hole) != "inside" for hole in holes)


def find_commune(lat: float, lon: float, communes: Sequence[dict[str, Any]]) -> Any | None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("invalid coordinates")
    for commune in communes:
        if any(_contains(lon, lat, polygon) for polygon in commune["polygons"]):
            return commune["id"]
    return None

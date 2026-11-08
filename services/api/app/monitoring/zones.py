"""Attention zones from a vigor-drop grid: connected pixels above the reference thresholds (R4-A1).

Thresholds are agronomic reference values supplied by the caller; without them nothing is detected. Pure numpy and
standard library, so the worker image carries a copy of this file.
"""
import itertools
import math
from collections import deque
from typing import Any

import numpy as np

PIXEL_HA = 0.01  # 10 m Sentinel-2 pixel
MAX_VERTICES = 200
Point = tuple[float, float]


def _dist(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    if n == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _douglas_peucker(points: list[Point], tol: float) -> list[Point]:
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        far, idx = -1.0, -1
        for i in range(lo + 1, hi):
            d = _dist(points[i], points[lo], points[hi])
            if d > far:
                far, idx = d, i
        if idx != -1 and far > tol:
            keep[idx] = True
            stack += [(lo, idx), (idx, hi)]
    return [p for p, k in zip(points, keep, strict=True) if k]


def simplify_ring(ring: list[Any], max_vertices: int = MAX_VERTICES) -> list[Any]:
    """A closed ring with at most `max_vertices` points (closing point included); a small ring is returned unchanged."""
    if len(ring) <= max_vertices:
        return list(ring)
    pts: list[Point] = [(float(x), float(y)) for x, y in ring]
    extent = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts)) or 1.0
    tol = extent * 1e-5
    for _ in range(80):
        out = _douglas_peucker(pts, tol)
        if len(out) <= max_vertices and len(out) >= 4:
            return out
        tol *= 1.5
    step = math.ceil(len(pts) / (max_vertices - 1))  # last resort: even subsampling
    out = pts[:-1:step]
    return [*out, out[0]]


def _components(mask: Any) -> list[list[tuple[int, int]]]:
    seen = np.zeros(mask.shape, dtype=bool)
    out: list[list[tuple[int, int]]] = []
    rows, cols = mask.shape
    for r0, c0 in zip(*np.nonzero(mask), strict=True):
        if seen[r0, c0]:
            continue
        seen[r0, c0] = True
        comp, queue = [], deque([(int(r0), int(c0))])
        while queue:
            r, c = queue.popleft()
            comp.append((r, c))
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True
                    queue.append((nr, nc))
        out.append(comp)
    return out


def _outer_ring(pixels: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Outline of a pixel set in grid corner coordinates (x = column, y = row); the largest loop, closed."""
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for r, c in pixels:
        for a, b in (((c, r), (c + 1, r)), ((c + 1, r), (c + 1, r + 1)), ((c + 1, r + 1), (c, r + 1)), ((c, r + 1), (c, r))):
            if (b, a) in edges:
                edges.discard((b, a))
            else:
                edges.add((a, b))
    nxt: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for a, b in edges:
        nxt.setdefault(a, []).append(b)
    best: list[tuple[int, int]] = []
    best_area = -1.0
    while nxt:
        start = next(iter(nxt))
        ring = [start]
        cur = start
        while True:
            cur = nxt[ring[-1]].pop()
            if not nxt[ring[-1]]:
                del nxt[ring[-1]]
            ring.append(cur)
            if cur == start or cur not in nxt:
                break
        area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in itertools.pairwise(ring))) / 2
        if ring[0] == ring[-1] and area > best_area:
            best, best_area = ring, area
    corners = [p for i, p in enumerate(best[:-1]) if _turns(best[i - 1], p, best[i + 1])]
    return [*corners, corners[0]] if corners else best


def _turns(a: tuple[int, int], b: tuple[int, int], c: tuple[int, int]) -> bool:
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0


def detect_zones(
    drop: Any, valid: Any, anomaly_drop: float | None, anomaly_min_pixels: int | None, bounds: tuple[float, float, float, float]
) -> list[dict[str, Any]]:
    """Zones (outline <= 200 vertices, centroid, pixels, mean drop, area), strongest first. No thresholds, no zone."""
    if anomaly_drop is None or anomaly_min_pixels is None:
        return []
    drop_arr = np.asarray(drop, dtype=float)
    mask = np.asarray(valid, dtype=bool) & (drop_arr >= anomaly_drop)
    minx, miny, maxx, maxy = bounds
    rows, cols = mask.shape
    dx, dy = (maxx - minx) / cols, (maxy - miny) / rows
    zones: list[dict[str, Any]] = []
    for comp in _components(mask):
        if len(comp) < anomaly_min_pixels:
            continue
        ring = [(minx + x * dx, maxy - y * dy) for x, y in _outer_ring(comp)]
        ring = simplify_ring(ring, MAX_VERTICES)
        clon = minx + (sum(c for _, c in comp) / len(comp) + 0.5) * dx
        clat = maxy - (sum(r for r, _ in comp) / len(comp) + 0.5) * dy
        score = float(np.mean([drop_arr[r, c] for r, c in comp]))
        zones.append({
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ring]]},
            "centroid": {"type": "Point", "coordinates": [clon, clat]},
            "pixels": len(comp), "drop_score": round(score, 6), "area_ha": round(len(comp) * PIXEL_HA, 6),
        })
    return sorted(zones, key=lambda z: (-z["drop_score"], -z["pixels"]))

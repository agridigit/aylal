"""F2 geometry rules (pure). Mirror of packages/domain/src/{geometry,area,overlap,block}.ts."""
import math
from typing import Any

Point = Any
Ring = Any
Json = dict[str, Any]

AUTHALIC_RADIUS_M = 6371007.2
MIN_VERTICES, MAX_VERTICES, MAX_IMPORT_FEATURES = 3, 500, 200
MIN_AREA_M2 = 1.0
MAX_IMPORT_VERTICES_TOTAL = 20000
SIMPLIFY_TOLERANCE_M = 1.5
OVERLAP_WARN_RATIO = 0.01
BLOCK_OVERFLOW_RATIO = 0.01
MOROCCO_EXTENT = {"min_lon": -17.2, "max_lon": -0.9, "min_lat": 20.7, "max_lat": 36.0}
M_PER_DEG = 111_194.9
TOUCH_EPS_M = 0.05


def area_m2(ring: Ring) -> float:
    n = len(ring)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        lon1, lat1 = ring[i][0], ring[i][1]
        lon2, lat2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        total += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total) * AUTHALIC_RADIUS_M**2 / 2


def area_ha(ring: Ring) -> float:
    return area_m2(ring) / 10_000


def display_area_ha(ha: float) -> float:
    return math.floor(ha * 100 + 0.5 + 1e-9) / 100


def open_ring(ring: Ring) -> list[list[float]]:
    out: list[list[float]] = []
    for p in ring:
        if not out or out[-1][0] != p[0] or out[-1][1] != p[1]:
            out.append([p[0], p[1]])
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _cross(o: Point, a: Point, b: Point) -> float:
    return float((a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]))


def _proper_crossing(a: Point, b: Point, c: Point, d: Point) -> list[float] | None:
    d1, d2, d3, d4 = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if d1 * d2 < 0 and d3 * d4 < 0:
        t = d3 / (d3 - d4)
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    return None


def self_crossings(pts: Ring) -> list[list[float]]:
    n = len(pts)
    out: list[list[float]] = []
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            x = _proper_crossing(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n])
            if x:
                out.append(x)
    return out


def validate_ring(inp: Ring) -> Json:
    # Raw length cap before any O(n^2) work (DoS): 500 vertices plus the closing point.
    if len(inp) > MAX_VERTICES + 1:
        return {"ok": False, "code": "too_many_vertices"}
    for p in inp:
        try:
            ok = len(p) >= 2 and math.isfinite(p[0]) and math.isfinite(p[1]) and abs(p[0]) <= 180 and abs(p[1]) <= 90
        except TypeError:
            ok = False
        if not ok:
            return {"ok": False, "code": "invalid_coordinates"}
    ring = open_ring(inp)
    distinct = len({(p[0], p[1]) for p in ring})
    if distinct < MIN_VERTICES:
        return {"ok": False, "code": "too_few_vertices"}
    if distinct > MAX_VERTICES:
        return {"ok": False, "code": "too_many_vertices"}
    crossings = self_crossings(ring)
    if crossings:
        return {"ok": False, "code": "self_intersection", "crossings": crossings}
    m2 = area_m2(ring)
    if m2 < MIN_AREA_M2:
        return {"ok": False, "code": "area_too_small"}
    return {"ok": True, "ring": ring, "area_ha": m2 / 10_000}


def is_in_morocco(point: Point) -> bool:
    e = MOROCCO_EXTENT
    return bool(e["min_lon"] <= point[0] <= e["max_lon"] and e["min_lat"] <= point[1] <= e["max_lat"])


def centroid(ring: Ring) -> list[float]:
    r = open_ring(ring)
    return [sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)]


def _dist_m(p: Point, a: Point, b: Point, cos_lat: float) -> float:
    ax, ay, bx, by = a[0] * cos_lat * M_PER_DEG, a[1] * M_PER_DEG, b[0] * cos_lat * M_PER_DEG, b[1] * M_PER_DEG
    px, py = p[0] * cos_lat * M_PER_DEG, p[1] * M_PER_DEG
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _douglas_peucker(pts: Ring, tol: float) -> list[list[float]]:
    if len(pts) < 3:
        return [[p[0], p[1]] for p in pts]
    cos_lat = math.cos(math.radians(pts[0][1]))
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        s, e = stack.pop()
        best, idx = -1.0, -1
        for i in range(s + 1, e):
            d = _dist_m(pts[i], pts[s], pts[e], cos_lat)
            if d > best:
                best, idx = d, i
        if idx >= 0 and best > tol:
            keep[idx] = True
            stack.extend([(s, idx), (idx, e)])
    return [[p[0], p[1]] for p, k in zip(pts, keep, strict=True) if k]


def simplify_track(points: Ring, tol: float = SIMPLIFY_TOLERANCE_M) -> list[list[float]]:
    out = _douglas_peucker(points, tol)
    while len(out) > MAX_VERTICES:
        tol *= 2
        out = _douglas_peucker(points, tol)
    return out


def import_features(geojson: Json) -> Json:
    entities: list[tuple[int, Any, Any]] = []
    for index, f in enumerate(geojson.get("features") or []):
        g = (f or {}).get("geometry") or {}
        props = (f or {}).get("properties") or {}
        if g.get("type") == "Polygon":
            coords = g.get("coordinates") or [[]]
            entities.append((index, coords[0], props))
        elif g.get("type") == "MultiPolygon":
            for poly in g.get("coordinates") or []:
                entities.append((index, (poly or [[]])[0], props))
        else:
            entities.append((index, None, props))
    if len(entities) > MAX_IMPORT_FEATURES:
        raise ValueError("too_many_features")
    if sum(len(open_ring(r)) for _, r, _ in entities if r is not None) > MAX_IMPORT_VERTICES_TOTAL:
        raise ValueError("too_many_vertices_total")
    result: Json = {"valid": [], "rejected": []}
    for index, ring, props in entities:
        if ring is None:
            result["rejected"].append({"index": index, "reason": "not_a_polygon"})
            continue
        r = validate_ring(ring)
        if r["ok"]:
            result["valid"].append({"ring": r["ring"], "area_ha": r["area_ha"], "properties": props})
        else:
            result["rejected"].append({"index": index, "reason": r["code"]})
    return result


# ---- planar helpers (overlap, contiguity, block containment) ----

def _project(ring: Ring, lon0: float, lat0: float) -> list[list[float]]:
    c = math.cos(math.radians(lat0))
    return [[(p[0] - lon0) * c * M_PER_DEG, (p[1] - lat0) * M_PER_DEG] for p in open_ring(ring)]


def _signed(p: Ring) -> float:
    return float(sum(a[0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * a[1] for i, a in enumerate(p)) / 2)


def _triangulate(poly: Ring) -> list[list[Point]]:
    p = list(reversed(poly)) if _signed(poly) < 0 else list(poly)
    tris: list[list[Point]] = []
    guard = len(p) * len(p) + 10
    while len(p) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for i in range(len(p)):
            a, b, c = p[i - 1], p[i], p[(i + 1) % len(p)]
            if _cross(a, b, c) <= 0:
                continue
            if any(q is not a and q is not b and q is not c and _cross(a, b, q) >= 0 and _cross(b, c, q) >= 0 and _cross(c, a, q) >= 0 for q in p):
                continue
            tris.append([a, b, c])
            del p[i]
            clipped = True
            break
        if not clipped:
            del p[0]
    if len(p) == 3:
        tris.append(list(p))
    return tris


def _inter(p: Point, q: Point, dp: float, dc: float) -> list[float]:
    t = dp / (dp - dc)
    return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]


def _clip_convex(subject: Ring, clip: Ring) -> list[Point]:
    out: list[Point] = list(subject)
    for i in range(len(clip)):
        if not out:
            break
        a, b = clip[i], clip[(i + 1) % len(clip)]
        src, out = out, []
        for j, cur in enumerate(src):
            prev = src[j - 1]
            dc, dp = _cross(a, b, cur), _cross(a, b, prev)
            if dc >= 0:
                if dp < 0:
                    out.append(_inter(prev, cur, dp, dc))
                out.append(cur)
            elif dp >= 0:
                out.append(_inter(prev, cur, dp, dc))
    return out


def intersection_area_m2(a: Ring, b: Ring) -> float:
    first = open_ring(a)[0]
    pa, pb = _project(a, first[0], first[1]), _project(b, first[0], first[1])
    subject = list(reversed(pa)) if _signed(pa) < 0 else pa
    return sum(abs(_signed(c)) if len(c) >= 3 else 0.0 for c in (_clip_convex(subject, t) for t in _triangulate(pb)))


def rings_touch(a: Ring, b: Ring) -> bool:
    first = open_ring(a)[0]
    pa, pb = _project(a, first[0], first[1]), _project(b, first[0], first[1])

    def seg_dist(p: Point, s: Point, e: Point) -> float:
        dx, dy = e[0] - s[0], e[1] - s[1]
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / l2))
        return math.hypot(p[0] - s[0] - t * dx, p[1] - s[1] - t * dy)

    for first_ring, second_ring in ((pa, pb), (pb, pa)):
        for p in first_ring:
            if any(seg_dist(p, second_ring[j], second_ring[(j + 1) % len(second_ring)]) <= TOUCH_EPS_M for j in range(len(second_ring))):
                return True
    for i in range(len(pa)):
        for j in range(len(pb)):
            s, e, c, d = pa[i], pa[(i + 1) % len(pa)], pb[j], pb[(j + 1) % len(pb)]
            if _cross(s, e, c) * _cross(s, e, d) < 0 and _cross(c, d, s) * _cross(c, d, e) < 0:
                return True
    return intersection_area_m2(a, b) > 0


def overlap_warnings(ring: Ring, others: Any) -> list[str]:
    mine = area_m2(ring)
    return [o["id"] for o in others if intersection_area_m2(ring, o["ring"]) > OVERLAP_WARN_RATIO * min(mine, area_m2(o["ring"]))]


def block_inside_field(block: Ring, field: Ring) -> bool:
    total = area_m2(block)
    return total > 0 and (total - intersection_area_m2(block, field)) / total <= BLOCK_OVERFLOW_RATIO

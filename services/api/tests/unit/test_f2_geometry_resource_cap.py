"""T075 - resource cap: raw ring length and total import vertices are bounded before any costly work (DoS)."""
import time

import pytest

from app.domain import geometry
from app.domain.geometry import MAX_VERTICES, import_features, validate_ring

CYCLE = [[-7.6, 33.57], [-7.598, 33.57], [-7.598, 33.572], [-7.599, 33.573], [-7.6, 33.572]]


def _no_crossings(_pts):
    raise AssertionError("self_crossings must not run on an oversized ring")


def _poly(n, lon=-7.6, lat=33.57, r=0.01):
    import math
    return [[lon + r * math.cos(2 * math.pi * i / n), lat + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


def test_given_a_huge_ring_of_repeated_points_when_validating_then_it_is_refused_fast_as_too_many_vertices_without_crossing_checks(monkeypatch):
    monkeypatch.setattr(geometry, "self_crossings", _no_crossings)
    ring = [CYCLE[i % 5] for i in range(100_000)]
    start = time.perf_counter()
    r = validate_ring(ring)
    assert time.perf_counter() - start < 0.1
    assert r == {"ok": False, "code": "too_many_vertices"}


def test_given_a_raw_ring_of_502_points_with_few_distinct_when_validating_then_it_is_refused_as_too_many_vertices(monkeypatch):
    monkeypatch.setattr(geometry, "self_crossings", _no_crossings)
    ring = [CYCLE[i % 5] for i in range(MAX_VERTICES + 2)]
    assert validate_ring(ring) == {"ok": False, "code": "too_many_vertices"}


def test_given_500_distinct_vertices_plus_the_closing_point_when_validating_then_it_is_still_accepted():
    p = _poly(500)
    assert validate_ring([*p, p[0]])["ok"] is True


def test_given_41_features_of_500_vertices_when_importing_then_the_total_cap_of_20000_raises_too_many_vertices_total(monkeypatch):
    monkeypatch.setattr(geometry, "self_crossings", _no_crossings)
    ring = [*_poly(500), _poly(500)[0]]
    gj = {"features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {}} for _ in range(41)]}
    with pytest.raises(ValueError, match="too_many_vertices_total"):
        import_features(gj)


def test_given_200_features_of_500_vertices_when_importing_then_the_total_cap_raises_too_many_vertices_total(monkeypatch):
    monkeypatch.setattr(geometry, "self_crossings", _no_crossings)
    ring = [*_poly(500), _poly(500)[0]]
    gj = {"features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {}} for _ in range(200)]}
    with pytest.raises(ValueError, match="too_many_vertices_total"):
        import_features(gj)


def test_given_200_features_of_100_vertices_when_importing_then_exactly_20000_vertices_are_accepted():
    ring = [*_poly(100), _poly(100)[0]]
    gj = {"features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {}} for _ in range(200)]}
    assert len(import_features(gj)["valid"]) == 200

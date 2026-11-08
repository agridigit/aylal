"""T061 - R4-A1: a zone with an abnormal vigor drop is delimited (polygon <= 200 vertices + centroid); thresholds come from the reference, never from code."""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from app.monitoring.zones import detect_zones, simplify_ring

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
V = json.loads((DOMAIN_DIR / "vectors/f3_anomaly.json").read_text(encoding="utf-8"))
P = V["params"]
BOUNDS = (-7.60, 33.57, -7.59, 33.58)  # minx, miny, maxx, maxy


def _grid(block, score, size=20):
    drop = np.zeros((size, size))
    drop[block] = score
    return drop, np.ones((size, size), dtype=bool)


def _run(drop, valid, **over):
    args = {"anomaly_drop": P["anomaly_drop"], "anomaly_min_pixels": P["anomaly_min_pixels"], "bounds": BOUNDS, **over}
    return detect_zones(drop, valid, **args)


def test_given_a_block_of_dropping_pixels_when_detecting_then_one_zone_is_delimited_with_polygon_and_centroid():
    drop, valid = _grid((slice(2, 7), slice(2, 7)), 0.3)  # 25 pixels
    zones = _run(drop, valid)
    assert len(zones) == 1
    z = zones[0]
    assert z["geometry"]["type"] == "Polygon" and z["centroid"]["type"] == "Point"
    lon, lat = z["centroid"]["coordinates"]
    assert BOUNDS[0] <= lon <= BOUNDS[2] and BOUNDS[1] <= lat <= BOUNDS[3]
    assert z["pixels"] == 25 and z["drop_score"] == pytest.approx(0.3)
    assert z["area_ha"] == pytest.approx(25 * 0.01)  # 10 m pixels = 0.01 ha


def test_given_a_block_smaller_than_the_minimum_when_detecting_then_nothing_is_reported():
    drop, valid = _grid((slice(2, 6), slice(2, 6)), 0.4)  # 16 < 20 pixels
    assert _run(drop, valid) == []


def test_given_a_drop_just_under_the_threshold_when_detecting_then_nothing_is_reported():
    drop, valid = _grid((slice(2, 8), slice(2, 8)), P["anomaly_drop"] - 0.0001)
    assert _run(drop, valid) == []


def test_given_a_drop_exactly_at_the_threshold_when_detecting_then_the_zone_is_reported():
    drop, valid = _grid((slice(2, 8), slice(2, 8)), P["anomaly_drop"])
    assert len(_run(drop, valid)) == 1


def test_given_two_separate_blocks_when_detecting_then_two_zones_are_reported():
    drop, valid = _grid((slice(0, 5), slice(0, 5)), 0.3)
    drop[10:16, 10:16] = 0.3
    assert len(_run(drop, valid)) == 2


def test_given_invalid_or_cloudy_pixels_when_detecting_then_they_never_form_a_zone():
    drop, valid = _grid((slice(2, 8), slice(2, 8)), 0.5)
    valid[2:8, 2:8] = False
    assert _run(drop, valid) == []


def test_given_missing_reference_thresholds_when_detecting_then_nothing_is_detected_and_no_default_is_assumed():
    drop, valid = _grid((slice(2, 8), slice(2, 8)), 0.9)
    assert _run(drop, valid, anomaly_drop=None, anomaly_min_pixels=None) == []


def test_given_an_irregular_outline_when_simplifying_then_the_ring_has_at_most_200_vertices_and_stays_closed():
    n = 1000
    ring = [(np.cos(2 * np.pi * i / n) * (1 + 0.001 * (i % 2)), np.sin(2 * np.pi * i / n) * (1 + 0.001 * (i % 2))) for i in range(n)]
    ring.append(ring[0])
    out = simplify_ring(ring, max_vertices=200)
    assert len(out) <= 200 and out[0] == out[-1]


def test_given_a_simple_ring_when_simplifying_then_it_is_unchanged():
    ring = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
    assert simplify_ring(ring, max_vertices=200) == ring

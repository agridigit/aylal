"""T021 - Python mirror of the drawing rules: declared area kept apart, irrigation, simplification (R1-A2, R1-A5, R3)."""
import math

import pytest

from app.domain.field_rules import validate_field
from app.domain.geometry import area_ha, display_area_ha, simplify_track

RING = [[-7.6, 33.57], [-7.599, 33.57], [-7.599, 33.571], [-7.6, 33.571], [-7.6, 33.57]]


def test_given_a_ring_when_displaying_the_area_then_it_has_two_decimals():
    assert display_area_ha(area_ha(RING)) == round(area_ha(RING), 2)


def test_given_a_declared_area_different_from_the_calculated_one_when_validating_then_both_are_returned_unchanged():
    r = validate_field({"name": "A", "ring": RING, "area_declared_ha": 7.5})
    assert r["ok"] and r["area_declared_ha"] == 7.5 and not math.isclose(r["area_ha"], 7.5)


def test_given_no_declared_area_when_validating_then_area_declared_ha_is_none():
    assert validate_field({"name": "A", "ring": RING})["area_declared_ha"] is None


@pytest.mark.parametrize("mode", ["rainfed", "gravity", "sprinkler", "drip", "pivot", None])
def test_given_a_known_irrigation_mode_or_none_when_validating_then_it_is_returned(mode):
    r = validate_field({"name": "A", "ring": RING, "irrigation": mode, "greenhouse": True})
    assert r["ok"] and r["irrigation"] == mode and r["greenhouse"] is True


def test_given_an_unknown_irrigation_or_a_non_boolean_greenhouse_when_validating_then_it_is_refused():
    assert validate_field({"name": "A", "ring": RING, "irrigation": "flood"})["code"] == "irrigation_invalid"
    assert validate_field({"name": "A", "ring": RING, "greenhouse": "yes"})["code"] == "greenhouse_invalid"


def test_given_a_dense_gps_walk_around_a_field_when_simplifying_then_at_most_500_vertices_keep_the_corners():
    corners = [(-7.6, 33.57), (-7.59, 33.57), (-7.59, 33.58), (-7.6, 33.58)]
    pts = []
    for (a, b), (c, d) in zip(corners, corners[1:] + corners[:1], strict=True):
        pts += [[a + (c - a) * i / 800, b + (d - b) * i / 800] for i in range(800)]
    out = simplify_track(pts)
    assert 4 <= len(out) <= 500
    assert all(any(math.isclose(p[0], c[0], abs_tol=1e-9) and math.isclose(p[1], c[1], abs_tol=1e-9) for p in out) for c in corners)

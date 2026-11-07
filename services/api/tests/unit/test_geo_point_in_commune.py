"""T011 - pure point-in-commune lookup (R4-A2). Coordinates are (lon, lat)."""
from app.geo.locate import find_commune

SQUARE = [[(0.0, 0.0), (0.0, 2.0), (2.0, 2.0), (2.0, 0.0), (0.0, 0.0)]]
HOLE = [
    [(10.0, 10.0), (10.0, 14.0), (14.0, 14.0), (14.0, 10.0), (10.0, 10.0)],
    [(11.0, 11.0), (11.0, 13.0), (13.0, 13.0), (13.0, 11.0), (11.0, 11.0)],
]
FAR = [[(20.0, 20.0), (20.0, 22.0), (22.0, 22.0), (22.0, 20.0), (20.0, 20.0)]]
COMMUNES = [
    {"id": "A", "polygons": [SQUARE[0], FAR[0]]},  # multi-polygon
    {"id": "B", "polygons": [HOLE]},  # polygon with a hole (list of rings)
]


def test_given_a_point_inside_a_commune_when_locating_then_its_id_is_returned():
    assert find_commune(lat=1.0, lon=1.0, communes=COMMUNES) == "A"


def test_given_a_point_in_the_second_polygon_of_a_multipolygon_then_the_commune_is_found():
    assert find_commune(lat=21.0, lon=21.0, communes=COMMUNES) == "A"


def test_given_a_point_outside_every_commune_when_locating_then_none_is_returned():
    assert find_commune(lat=48.85, lon=2.35, communes=COMMUNES) is None


def test_given_a_point_in_a_hole_when_locating_then_none_is_returned():
    assert find_commune(lat=12.0, lon=12.0, communes=COMMUNES) is None


def test_given_a_point_in_the_ring_around_the_hole_then_the_commune_is_found():
    assert find_commune(lat=10.5, lon=10.5, communes=COMMUNES) == "B"


def test_given_a_point_on_the_boundary_then_it_counts_as_inside():
    assert find_commune(lat=0.0, lon=1.0, communes=COMMUNES) == "A"


def test_given_swapped_lat_lon_then_the_point_is_not_matched():
    assert find_commune(lat=21.0, lon=1.0, communes=COMMUNES) is None


def test_given_invalid_coordinates_then_a_value_error_is_raised():
    import pytest

    with pytest.raises(ValueError):
        find_commune(lat=91.0, lon=0.0, communes=COMMUNES)

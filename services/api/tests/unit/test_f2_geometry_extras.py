"""T009 - Python mirror of the Morocco extent, track simplification and GeoJSON import rules."""


def test_given_points_when_checking_the_national_extent_then_morocco_is_in_and_europe_is_out():
    from app.domain.geometry import is_in_morocco

    assert is_in_morocco((-7.6, 33.57)) and is_in_morocco((-15.95, 23.7))
    assert not is_in_morocco((2.35, 48.85)) and not is_in_morocco((-3.7, 40.4))


def test_given_a_noisy_track_when_simplifying_then_at_most_500_vertices_remain():
    import math

    from app.domain.geometry import simplify_track

    pts = [[-7.6 + 0.01 * math.cos(2 * math.pi * i / 2000), 33.57 + 0.01 * math.sin(2 * math.pi * i / 2000)] for i in range(2000)]
    assert len(simplify_track(pts)) <= 500


def test_given_a_multipolygon_and_a_point_when_importing_then_split_and_rejected():
    from app.domain.geometry import import_features

    sq = [[-7.6, 33.57], [-7.599, 33.57], [-7.599, 33.571], [-7.6, 33.571], [-7.6, 33.57]]
    sq2 = [[x + 0.1, y] for x, y in sq]
    feats = [
        {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": [[sq], [sq2]]}},
        {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [-7.6, 33.57]}},
    ]
    r = import_features({"type": "FeatureCollection", "features": feats})
    assert len(r["valid"]) == 2
    assert [x["reason"] for x in r["rejected"]] == ["not_a_polygon"]

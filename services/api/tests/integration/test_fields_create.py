"""T023 - POST/PATCH/archive of fields (R1-A2 to R1-A5, edge cases)."""
import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_field, new_user, square


@pytest.fixture
def ctx(make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    return dict(farm=farm, h=auth(token_for(owner)), owner=owner)


def post(client, c, body):
    return client.post(f"/v1/farms/{c['farm']}/fields", json=body, headers=c["h"])


def test_given_a_drawn_polygon_when_creating_then_201_with_the_postgis_area_and_no_warning(client, ctx):
    r = post(client, ctx, {"name": "Nord", "geometry": square(), "source": "draw_taps"})
    assert r.status_code == 201, r.text
    body = r.json()
    expected = sql("SELECT ST_Area(geometry::geography)/10000 FROM parcels WHERE id=$1", __import__("uuid").UUID(body["id"]))[0][0]
    assert body["area_calc_ha"] == pytest.approx(float(expected), rel=0.005)
    assert body["warnings"] == [] and body["farm_id"] == str(ctx["farm"])


def test_given_a_client_area_calc_ha_when_creating_then_it_is_ignored_and_the_server_value_is_kept(client, ctx):
    r = post(client, ctx, {"name": "A", "geometry": square(), "area_calc_ha": 9999})
    assert r.status_code == 201 and r.json()["area_calc_ha"] < 100


def test_given_a_declared_area_different_from_the_calculated_one_when_creating_then_both_are_kept_apart(client, ctx):
    r = post(client, ctx, {"name": "A", "geometry": square(), "area_declared_ha": 7.5})
    assert r.status_code == 201
    assert r.json()["area_declared_ha"] == 7.5 and r.json()["area_calc_ha"] != 7.5


def test_given_a_self_crossing_polygon_when_creating_then_422_and_nothing_is_stored(client, ctx):
    bow = {"type": "Polygon", "coordinates": [[[-7.6, 33.57], [-7.598, 33.572], [-7.598, 33.57], [-7.6, 33.572], [-7.6, 33.57]]]}
    r = post(client, ctx, {"name": "Bow", "geometry": bow})
    assert r.status_code == 422 and "self_intersect" in r.text
    assert sql("SELECT count(*) FROM parcels")[0][0] == 0


@pytest.mark.parametrize("ring", [
    [[-7.6, 33.57], [-7.598, 33.57], [-7.6, 33.57]],                                  # fewer than 3 distinct points
    [[-7.6, 33.57], [-7.59, 33.57], [-7.58, 33.57], [-7.6, 33.57]],                   # collinear: zero area
])
def test_given_fewer_than_three_points_or_a_zero_area_when_creating_then_422(client, ctx, ring):
    assert post(client, ctx, {"name": "Flat", "geometry": {"type": "Polygon", "coordinates": [ring]}}).status_code == 422


def test_given_501_vertices_when_creating_then_422(client, ctx):
    import math
    ring = [[-7.6 + 0.01 * math.cos(2 * math.pi * i / 501), 33.57 + 0.01 * math.sin(2 * math.pi * i / 501)] for i in range(501)]
    assert post(client, ctx, {"name": "Big", "geometry": {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}}).status_code == 422


def test_given_a_polygon_outside_morocco_when_creating_then_422_outside_morocco(client, ctx):
    r = post(client, ctx, {"name": "Paris", "geometry": square(2.35, 48.85)})
    assert r.status_code == 422 and "outside_morocco" in r.text
    assert sql("SELECT count(*) FROM parcels")[0][0] == 0


def test_given_a_polygon_above_5000_ha_when_creating_then_422(client, ctx):
    assert post(client, ctx, {"name": "Huge", "geometry": square(-7.6, 33.0, 0.5)}).status_code == 422


def test_given_a_name_longer_than_80_characters_or_blank_when_creating_then_422(client, ctx):
    assert post(client, ctx, {"name": "x" * 81, "geometry": square()}).status_code == 422
    assert post(client, ctx, {"name": "  ", "geometry": square()}).status_code == 422


def test_given_a_polygon_overlapping_an_existing_field_when_creating_then_201_with_a_non_blocking_warning(client, ctx):
    other = add_field(ctx["farm"], "Existing", lon=-7.60)
    r = post(client, ctx, {"name": "Overlap", "geometry": square(-7.601)})
    assert r.status_code == 201
    assert {"code": "overlap", "field_id": str(other)} in r.json()["warnings"]


def test_given_a_farm_with_500_fields_when_creating_one_more_then_422_field_limit_reached(client, ctx):
    sql(
        "INSERT INTO parcels (id, farm_id, name, geometry) SELECT gen_random_uuid(), $1, 'F'||g, "
        "ST_SetSRID(ST_GeomFromGeoJSON($2), 4326) FROM generate_series(1, 500) g",
        ctx["farm"], __import__("json").dumps(square(-7.0)),
    )
    r = post(client, ctx, {"name": "501", "geometry": square(-7.9)})
    assert r.status_code == 422 and "field_limit_reached" in r.text


def test_given_a_field_when_patching_its_name_and_geometry_then_the_area_is_recomputed(client, ctx):
    fid = post(client, ctx, {"name": "A", "geometry": square()}).json()["id"]
    r = client.patch(f"/v1/farms/{ctx['farm']}/fields/{fid}", json={"name": "B", "geometry": square(-7.6, 33.57, 0.004)}, headers=ctx["h"])
    assert r.status_code == 200 and r.json()["name"] == "B" and r.json()["area_calc_ha"] > 10


def test_given_a_field_when_archiving_then_it_leaves_the_list_and_can_be_restored_within_90_days(client, ctx):
    fid = post(client, ctx, {"name": "A", "geometry": square()}).json()["id"]
    base = f"/v1/farms/{ctx['farm']}/fields"
    assert client.delete(f"{base}/{fid}", headers=ctx["h"]).status_code == 204
    assert client.get(f"{base}/{fid}", headers=ctx["h"]).status_code == 404
    assert [f["id"] for f in client.get(f"{base}/archived", headers=ctx["h"]).json()["items"]] == [fid]
    assert client.post(f"{base}/{fid}/restore", headers=ctx["h"]).status_code == 200

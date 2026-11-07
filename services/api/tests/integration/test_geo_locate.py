"""T011 - geo reference and point-in-commune over PostGIS (R4-A2)."""
import uuid

from tests.helpers import auth


def _h(token_for):
    return auth(token_for(uuid.uuid4()))


def test_given_the_reference_when_listing_regions_then_the_regions_of_morocco_are_returned(client, token_for):
    r = client.get("/v1/geo/regions", headers=_h(token_for))
    assert r.status_code == 200
    regions = r.json()
    assert len(regions) >= 12
    assert {"id", "name_ar", "name_fr"} <= set(regions[0])


def test_given_a_province_when_listing_communes_then_only_its_communes_are_returned(client, token_for):
    h = _h(token_for)
    provinces = client.get("/v1/geo/provinces", headers=h)
    assert provinces.status_code == 200
    pid = provinces.json()[0]["id"]
    r = client.get("/v1/geo/communes", params={"province": pid}, headers=h)
    assert r.status_code == 200 and len(r.json()) >= 1
    assert all(c["province_id"] == pid for c in r.json())


def test_given_a_point_in_casablanca_when_locating_then_its_commune_is_returned(client, token_for):
    r = client.get("/v1/geo/locate", params={"lat": 33.5731, "lon": -7.5898}, headers=_h(token_for))
    assert r.status_code == 200
    assert {"id", "name_fr", "province_id"} <= set(r.json())


def test_given_a_point_in_paris_when_locating_then_404(client, token_for):
    r = client.get("/v1/geo/locate", params={"lat": 48.8566, "lon": 2.3522}, headers=_h(token_for))
    assert r.status_code == 404


def test_given_a_point_in_the_ocean_when_locating_then_404(client, token_for):
    r = client.get("/v1/geo/locate", params={"lat": 30.0, "lon": -20.0}, headers=_h(token_for))
    assert r.status_code == 404


def test_given_out_of_range_coordinates_when_locating_then_422(client, token_for):
    r = client.get("/v1/geo/locate", params={"lat": 123, "lon": 0}, headers=_h(token_for))
    assert r.status_code == 422

"""T044 - /v1/phyto-products, /v1/farms/{farm_id}/phyto-products/free and the label analysis conform to the contract."""
from tests.contract._f6_spec import PATHS, SCHEMAS, codes
from tests.helpers import auth
from tests.integration._f6 import world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32


def test_given_the_contract_then_catalogue_free_product_and_label_routes_are_documented_with_their_codes():
    assert "200" in codes("/v1/phyto-products", "get")
    assert {"200", "422"} <= codes("/v1/farms/{farm_id}/phyto-products/free", "post")
    assert {"200", "413", "422", "503"} <= codes("/v1/farms/{farm_id}/operations/label", "post")
    assert {"200"} <= codes("/v1/farms/{farm_id}/operations/check", "post")
    assert SCHEMAS["FreeProductRequest"]["additionalProperties"] is False


def test_given_a_search_then_the_response_has_items_with_active_ingredients_and_the_catalogue_version(client, token_for, world):
    add_product(add_catalog(), "Cuprex")
    r = client.get("/v1/phyto-products", headers=auth(token_for(world["owner"])), params={"q": "cup"})
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"items", "catalog_version"} and r.json()["catalog_version"]["source_date"]
    assert {"id", "name", "active_ingredients"} <= set(r.json()["items"][0])


def test_given_a_free_product_then_200_with_its_name_flagged_free_and_422_for_invalid_names(client, token_for, world):
    w = world
    url = f"/v1/farms/{w['farm_a']}/phyto-products/free"
    h = auth(token_for(w["worker"]))
    assert client.post(url, headers=h, json={"name": "Maison"}).json() == {"name": "Maison", "is_free": True}
    for body in ({"name": ""}, {"name": "x" * 81}, {"name": "ok", "url": "https://x"}, {}):
        assert client.post(url, headers=h, json=body).status_code == 422, body


def test_given_a_label_analysis_then_the_documented_503_carries_code_and_photo_id_and_the_documented_statuses_hold(client, token_for, world):
    w = world
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/label", headers=auth(token_for(w["owner"])), files={"photo": ("l.jpg", JPEG, "image/jpeg")})
    assert r.status_code in (200, 503)
    assert {"label_photo_id", "candidates"} <= set(r.json())
    if r.status_code == 503:
        assert r.json()["code"] == "label_unavailable"
    bad = client.post(f"/v1/farms/{w['farm_a']}/operations/label", headers=auth(token_for(w["owner"])), files={"photo": ("l.png", b"\x89PNG0000", "image/png")})
    assert bad.status_code == 422
    assert PATHS["/v1/farms/{farm_id}/operations/label"]["post"]["responses"]["422"]

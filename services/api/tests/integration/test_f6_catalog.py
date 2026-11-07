"""T043 - R2-A1: catalogue search by name and active ingredient, expired homologation hidden but kept, version date."""
import datetime as dt

from tests.helpers import auth, sql
from tests.integration._f6 import op_body, world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product, crops, grow


def search(client, token_for, who, **params):
    return client.get("/v1/phyto-products", headers=auth(token_for(who)), params=params)


def test_given_the_catalogue_when_searching_by_name_then_the_matching_products_come_with_their_active_ingredient(client, token_for, world):
    v = add_catalog()
    add_product(v, "Cuprex 50", ingredients=[{"name": "cuivre", "concentration": "50%"}])
    add_product(v, "Soufrex", ingredients=[{"name": "soufre", "concentration": "80%"}])
    r = search(client, token_for, world["owner"], q="cupr")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [i["name"] for i in items] == ["Cuprex 50"]
    assert items[0]["active_ingredients"] == [{"name": "cuivre", "concentration": "50%"}]


def test_given_an_active_ingredient_when_searching_then_products_containing_it_are_found(client, token_for, world):
    v = add_catalog()
    add_product(v, "Brand A", ingredients=[{"name": "soufre", "concentration": "80%"}])
    assert [i["name"] for i in search(client, token_for, world["owner"], q="soufre").json()["items"]] == ["Brand A"]


def test_given_a_worker_when_searching_then_the_catalogue_is_readable(client, token_for, world):
    add_product(add_catalog(), "Cuprex")
    assert search(client, token_for, world["worker"], q="cup").status_code == 200


def test_given_no_token_when_searching_then_401(client):
    assert client.get("/v1/phyto-products", params={"q": "cu"}).status_code == 401


def test_given_a_wildcard_in_the_query_when_searching_then_it_is_matched_literally(client, token_for, world):
    add_product(add_catalog(), "Cuprex")
    for q in ("%", "_", "c_prex"):
        assert search(client, token_for, world["owner"], q=q).json()["items"] == [], q


def test_given_an_expired_homologation_when_searching_then_the_product_is_hidden_but_kept_in_the_database(client, token_for, world):
    v = add_catalog()
    old = add_product(v, "Cuprex ancien", expired=True)
    add_product(v, "Cuprex neuf")
    assert [i["name"] for i in search(client, token_for, world["owner"], q="cuprex").json()["items"]] == ["Cuprex neuf"]
    assert sql("SELECT count(*) FROM phyto_products WHERE id=$1", old)[0][0] == 1


def test_given_a_past_treatment_with_a_product_that_later_expired_then_the_registry_line_keeps_its_name(client, token_for, world):
    w = world
    (cid, slug), = crops(1)
    grow(w["farm_a"], w["a1"], cid)
    v = add_catalog()
    pid = add_product(v, "Cuprex", [dict(crop_slug=slug, max_dose=2, dar_days=7)])
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])),
                    json=op_body([w["a1"]], type="phyto", product_id=str(pid), dose=1, dose_unit="L/ha"))
    assert r.status_code == 201, r.text
    sql("UPDATE phyto_products SET expired_at=now() WHERE id=$1", pid)
    assert search(client, token_for, w["owner"], q="cuprex").json()["items"] == []
    entries = client.get(f"/v1/farms/{w['farm_a']}/registry", headers=auth(token_for(w["owner"]))).json()["items"]
    assert [e["product_name"] for e in entries] == ["Cuprex"]


def test_given_a_catalogue_version_when_searching_then_its_source_date_is_returned_for_offline_display(client, token_for, world):
    add_catalog(dt.date(2026, 8, 1))
    newest = add_catalog(dt.date(2026, 10, 1))
    sql("UPDATE catalog_versions SET imported_at = now() + interval '1 minute' WHERE id=$1", newest)
    body = search(client, token_for, world["owner"], q="").json()
    assert body["catalog_version"]["source_date"] == "2026-10-01"


def test_given_a_crop_filter_when_searching_then_only_products_authorised_on_that_crop_are_returned(client, token_for, world):
    (_, tomato), (_, olive) = crops(2)
    v = add_catalog()
    add_product(v, "Tomatex", [dict(crop_slug=tomato, max_dose=1)])
    add_product(v, "Olivex", [dict(crop_slug=olive, max_dose=1)])
    assert [i["name"] for i in search(client, token_for, world["owner"], q="ex", crop=tomato).json()["items"]] == ["Tomatex"]


def test_given_a_limit_above_the_cap_when_searching_then_422(client, token_for, world):
    assert search(client, token_for, world["owner"], q="a", limit=51).status_code == 422


def test_given_an_oversized_query_when_searching_then_422(client, token_for, world):
    assert search(client, token_for, world["owner"], q="x" * 81).status_code == 422


def test_given_a_second_catalogue_import_when_searching_then_only_the_latest_version_is_returned(client, token_for, world):
    old = add_catalog(dt.date(2026, 8, 1))
    add_product(old, "Cuprex 50")
    add_product(old, "Retired only")
    new = add_catalog(dt.date(2026, 10, 1))
    sql("UPDATE catalog_versions SET imported_at = now() + interval '1 minute' WHERE id=$1", new)
    add_product(new, "Cuprex 50")
    items = search(client, token_for, world["owner"], q="").json()["items"]
    assert sorted(i["name"] for i in items) == ["Cuprex 50"]

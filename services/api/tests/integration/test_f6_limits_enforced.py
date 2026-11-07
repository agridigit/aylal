"""T016 - G3: caps are enforced before any costly work; unbounded lists never exist."""
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_field, op_body, sync_op, world  # noqa: F401


def _post(client, token_for, w, body, who="owner"):
    return client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w[who])), json=body)


def test_given_a_valid_operation_then_201(client, token_for, world):
    assert _post(client, token_for, world, op_body([world["a1"]])).status_code == 201


def test_given_51_parcels_then_422_and_nothing_written(client, token_for, world):
    w = world
    parcels = [w["a1"]] + [uuid.uuid4() for _ in range(50)]
    assert _post(client, token_for, w, op_body([w["a1"]])).status_code == 201
    r = _post(client, token_for, w, op_body(parcels))
    assert r.status_code == 422, r.text
    assert sql("SELECT count(*) FROM operations")[0][0] == 1


def test_given_out_of_bounds_values_then_422(client, token_for, world):
    w = world
    assert _post(client, token_for, w, op_body([w["a1"]], note="x" * 500)).status_code == 201
    for extra in ({"note": "x" * 501}, {"dose": 0}, {"dose": 100000.001}, {"dose": 1.2345}, {"free_product_name": "x" * 81},
                  {"operator_name": "x" * 81}, {"performed_on": "1999-12-31"}, {"quantity_total": -1}):
        assert _post(client, token_for, w, op_body([w["a1"]], **extra)).status_code == 422, extra


def test_given_six_product_lines_then_422(client, token_for, world):
    w = world
    lines = [{"free_product_name": f"p{i}", "dose": 1, "dose_unit": "L/ha"} for i in range(6)]
    assert _post(client, token_for, w, op_body([w["a1"]], type="phyto", product_lines=lines[:5])).status_code == 201
    assert _post(client, token_for, w, op_body([w["a1"]], type="phyto", product_lines=lines)).status_code == 422


def test_given_a_huge_body_then_413_from_the_declared_size_before_any_parsing(client, token_for, world):
    w = world
    assert _post(client, token_for, w, op_body([w["a1"]])).status_code == 201
    body = ('{"note":"' + "x" * (2 * 1024 * 1024) + '"}').encode()
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers={**auth(token_for(w["owner"])), "content-type": "application/json"},
                    content=body)
    assert r.status_code == 413, r.status_code  # size is read first: 413, not the 422 a parse would give


def test_given_a_sync_batch_of_101_operations_then_413_batch_too_large_before_any_write(client, token_for, world):
    w = world
    ok = client.post("/v1/sync/upload", headers=auth(token_for(w["owner"])), json={"ops": [sync_op(
        "operations", w["farm_a"], uuid.uuid4(), {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]})]})
    assert ok.status_code == 200, ok.text
    before = sql("SELECT count(*) FROM operations")[0][0]
    ops = [sync_op("operations", w["farm_a"], uuid.uuid4(), {"type": "irrigation", "performed_on": TODAY.isoformat(),
                                                             "parcel_ids": [str(w["a1"])]}) for _ in range(101)]
    r = client.post("/v1/sync/upload", headers=auth(token_for(w["owner"])), json={"ops": ops})
    assert r.status_code == 413, r.text
    assert "batch_too_large" in r.text
    assert sql("SELECT count(*) FROM operations")[0][0] == before


def test_given_a_label_photo_over_3mb_or_wrong_type_then_refused(client, token_for, world):
    w = world
    url = f"/v1/farms/{w['farm_a']}/operations/label"
    h = auth(token_for(w["owner"]))
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 1024
    ok = client.post(url, headers=h, files={"photo": ("a.jpg", jpeg, "image/jpeg")})
    assert ok.status_code in (200, 503), ok.text
    assert client.post(url, headers=h, files={"photo": ("a.jpg", b"\xff\xd8\xff\xe0" + b"0" * (3 * 1024 * 1024 + 1), "image/jpeg")}).status_code == 413
    assert client.post(url, headers=h, files={"photo": ("a.jpg", b"GIF89a" + b"0" * 100, "image/jpeg")}).status_code == 422
    assert client.post(url, headers=h, files={"photo": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}).status_code == 422


def test_given_pagination_then_limit_201_is_422_and_the_default_page_is_50(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    assert client.get(f"/v1/farms/{w['farm_a']}/operations?limit=200", headers=h).status_code == 200
    assert client.get(f"/v1/farms/{w['farm_a']}/operations?limit=201", headers=h).status_code == 422
    for _ in range(55):
        assert _post(client, token_for, w, op_body([w["a1"]])).status_code == 201
    page = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=h).json()
    assert len(page["items"]) == 50 and page.get("next_cursor")

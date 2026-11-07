"""T045 - R2-A2: the LabelRecognizer port. Unavailable -> name fallback; a recognition is only proposed, never recorded."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import op_body, world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"0" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class FakeRecognizer:
    def __init__(self, candidates=None, fail=False):
        self.candidates, self.fail, self.calls = candidates or [], fail, 0

    async def recognize(self, data: bytes):
        self.calls += 1
        if self.fail:
            raise TimeoutError("vision down")
        return self.candidates


@pytest.fixture
def recognizer(client):
    from app.main import app
    from app.operations import label

    def install(fake):
        app.dependency_overrides[label.get_recognizer] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(label.get_recognizer, None)


def upload(client, token_for, who, farm, data=JPEG, ctype="image/jpeg"):
    return client.post(f"/v1/farms/{farm}/operations/label", headers=auth(token_for(who)), files={"photo": ("label.jpg", data, ctype)})


def test_given_no_vision_url_when_scanning_a_label_then_the_recognizer_is_unavailable_and_name_search_remains(client, token_for, world, monkeypatch):
    monkeypatch.setenv("AYLAL_VISION_URL", "")
    r = upload(client, token_for, world["owner"], world["farm_a"])
    assert r.status_code == 503 and r.json()["code"] == "label_unavailable"
    assert uuid.UUID(r.json()["label_photo_id"]) and r.json()["candidates"] == []
    assert client.get("/v1/phyto-products", headers=auth(token_for(world["owner"])), params={"q": "a"}).status_code == 200


def test_given_a_recognised_product_when_scanning_then_it_is_proposed_for_confirmation_and_nothing_is_recorded(client, token_for, world, recognizer):
    pid = add_product(add_catalog(), "Cuprex")
    recognizer(FakeRecognizer([{"product_id": str(pid), "name": "Cuprex", "confidence": 0.93}]))
    ops, registry = sql("SELECT count(*) FROM operations")[0][0], sql("SELECT count(*) FROM registry_entries")[0][0]
    r = upload(client, token_for, world["owner"], world["farm_a"])
    assert r.status_code == 200, r.text
    assert [c["product_id"] for c in r.json()["candidates"]] == [str(pid)]
    assert (sql("SELECT count(*) FROM operations")[0][0], sql("SELECT count(*) FROM registry_entries")[0][0]) == (ops, registry)
    assert sql("SELECT consumed_at FROM label_uploads WHERE id=$1", uuid.UUID(r.json()["label_photo_id"]))[0][0] is None


def test_given_a_candidate_outside_the_catalogue_or_expired_when_scanning_then_it_is_not_proposed(client, token_for, world, recognizer):
    expired = add_product(add_catalog(), "Vieux", expired=True)
    recognizer(FakeRecognizer([{"product_id": str(uuid.uuid4()), "name": "Ghost", "confidence": 0.9},
                               {"product_id": str(expired), "name": "Vieux", "confidence": 0.9}]))
    r = upload(client, token_for, world["owner"], world["farm_a"])
    assert r.status_code == 200 and r.json()["candidates"] == []


def test_given_a_recognizer_that_fails_when_scanning_then_503_with_the_photo_id_for_the_name_fallback(client, token_for, world, recognizer):
    recognizer(FakeRecognizer(fail=True))
    r = upload(client, token_for, world["owner"], world["farm_a"])
    assert r.status_code == 503 and r.json()["code"] == "label_unavailable"
    assert sql("SELECT count(*) FROM label_uploads WHERE id=$1", uuid.UUID(r.json()["label_photo_id"]))[0][0] == 1


def test_given_a_valid_photo_then_the_server_names_the_object_and_binds_it_to_farm_and_user(client, token_for, world, recognizer):
    recognizer(FakeRecognizer())
    w = world
    r = upload(client, token_for, w["worker"], w["farm_a"], WEBP, "image/webp")
    assert r.status_code == 200, r.text
    row = sql("SELECT farm_id, user_id, object_key FROM label_uploads WHERE id=$1", uuid.UUID(r.json()["label_photo_id"]))[0]
    assert (row["farm_id"], row["user_id"]) == (w["farm_a"], w["worker"])
    assert row["object_key"].startswith(f"farms/{w['farm_a']}/labels/")
    assert row["object_key"] not in r.text


def test_given_a_photo_over_3_mb_when_scanning_then_413_and_the_recognizer_is_not_called(client, token_for, world, recognizer):
    fake = recognizer(FakeRecognizer())
    r = upload(client, token_for, world["owner"], world["farm_a"], JPEG + b"0" * (3 * 1024 * 1024))
    assert r.status_code == 413
    assert fake.calls == 0


def test_given_a_non_jpeg_or_webp_signature_when_scanning_then_422_whatever_the_declared_type(client, token_for, world, recognizer):
    fake = recognizer(FakeRecognizer())
    assert upload(client, token_for, world["owner"], world["farm_a"], PNG, "image/jpeg").status_code == 422
    assert upload(client, token_for, world["owner"], world["farm_a"], b"GIF89a" + b"0" * 20, "image/webp").status_code == 422
    assert fake.calls == 0


def test_given_a_label_photo_id_of_another_user_when_recording_then_422_invalid_object_ref(client, token_for, world, recognizer):
    recognizer(FakeRecognizer())
    w = world
    lid = upload(client, token_for, w["worker"], w["farm_a"]).json()["label_photo_id"]
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=op_body([w["a1"]], type="phyto", label_photo_id=lid))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_object_ref"
    assert sql("SELECT consumed_at FROM label_uploads WHERE id=$1", uuid.UUID(lid))[0][0] is None


def test_given_a_client_chosen_object_key_or_url_when_recording_then_it_is_rejected_and_nothing_is_written(client, token_for, world):
    w = world
    before = sql("SELECT count(*) FROM operations")[0][0]
    for field, value in (("label_photo_key", f"farms/{w['farm_b']}/labels/{uuid.uuid4()}"), ("label_photo_url", "https://evil/x.jpg")):
        r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=op_body([w["a1"]], type="phyto", **{field: value}))
        assert r.status_code == 422, r.text
    assert sql("SELECT count(*) FROM operations")[0][0] == before


def test_given_the_label_module_then_it_exposes_the_recognizer_port_and_its_provider():
    from app.operations import label

    assert hasattr(label, "LabelRecognizer") and hasattr(label, "get_recognizer")

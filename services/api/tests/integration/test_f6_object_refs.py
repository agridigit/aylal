"""T022a - G1: object references (IDOR). Clients never name a storage key; ids are server-issued and scoped to (farm, user)."""
import io
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, op_body, sync_op, world  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512
EXPORT = {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "pdf", "scope": "farm", "lang": "fr"}
FORGED = ["label_photo_key", "file_keys"]


def _label(client, token_for, w, who, farm):
    r = client.post(f"/v1/farms/{farm}/operations/label", headers=auth(token_for(w[who])),
                    files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert r.status_code in (200, 503), r.text
    return r.json()["label_photo_id"]


def _rest(client, token_for, w, who, farm, parcel, **extra):
    return client.post(f"/v1/farms/{farm}/operations", headers=auth(token_for(w[who])), json=op_body([parcel], type="phyto", **extra))


def _sync(client, token_for, w, who, farm, parcel, **extra):
    fields = {k: v for k, v in op_body([parcel], type="phyto", **extra).items() if k != "id"}
    return client.post("/v1/sync/upload", headers=auth(token_for(w[who])), json={"ops": [sync_op("operations", farm, uuid.uuid4(), fields)]})


def test_given_a_label_issued_to_me_in_this_farm_when_attaching_it_then_it_is_consumed_once_and_never_exposed(client, token_for, world):
    w = world
    lid = _label(client, token_for, w, "owner", w["farm_a"])
    r = _rest(client, token_for, w, "owner", w["farm_a"], w["a1"], label_photo_id=lid)
    assert r.status_code == 201, r.text
    assert "label_photo_key" not in r.text and "farms/" not in r.text
    assert sql("SELECT label_photo_key FROM operations WHERE id=$1", uuid.UUID(r.json()["id"]))[0][0].startswith(f"farms/{w['farm_a']}/labels/")
    again = _rest(client, token_for, w, "owner", w["farm_a"], w["a1"], label_photo_id=lid)
    assert again.status_code == 422 and again.json()["detail"]["code"] == "invalid_object_ref"


@pytest.mark.parametrize("channel", ["rest", "sync"])
def test_given_a_label_id_of_farm_b_or_of_another_user_or_unknown_when_presented_then_422_invalid_object_ref(client, token_for, world, channel):
    w = world
    send = _rest if channel == "rest" else _sync
    ok = send(client, token_for, w, "owner", w["farm_a"], w["a1"], label_photo_id=_label(client, token_for, w, "owner", w["farm_a"]))
    assert ok.status_code in (200, 201), ok.text
    foreign_farm = _label(client, token_for, w, "owner_b", w["farm_b"])
    other_user = _label(client, token_for, w, "manager", w["farm_a"])
    before = sql("SELECT count(*) FROM operations")[0][0]
    bodies = []
    for lid in (foreign_farm, other_user, str(uuid.uuid4())):
        r = send(client, token_for, w, "owner", w["farm_a"], w["a1"], label_photo_id=lid)
        if channel == "rest":
            assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_object_ref", r.text
            bodies.append(r.text)
        else:
            assert r.status_code == 200 and r.json()["results"][0]["status"] == "rejected", r.text
            assert r.json()["results"][0]["error"]["code"] == "invalid_object_ref"
    assert len(set(bodies)) <= 1, "responses must be identical (no oracle)"
    assert sql("SELECT count(*) FROM operations")[0][0] == before


@pytest.mark.parametrize("channel", ["rest", "sync"])
@pytest.mark.parametrize("forged", [
    {"label_photo_key": "farms/x/labels/y"}, {"file_keys": ["a"]}, {"label_photo_key": "../etc/passwd"},
    {"label_photo_key": "http://evil.test/x"}, {"label_photo_id": "https://evil.test/x"},
    {"label_photo_key": f"farms/{uuid.uuid4()}/labels/{uuid.uuid4()}"},
])
def test_given_a_raw_storage_key_or_url_in_a_body_then_it_is_refused_and_never_written(client, token_for, world, channel, forged):
    w = world
    send = _rest if channel == "rest" else _sync
    ok = send(client, token_for, w, "owner", w["farm_a"], w["a1"])
    assert ok.status_code in (200, 201), ok.text
    before = sql("SELECT count(*) FROM operations")[0][0]
    r = send(client, token_for, w, "owner", w["farm_a"], w["a1"], **forged)
    if channel == "rest":
        assert r.status_code == 422, r.text
    else:
        assert r.status_code == 200 and r.json()["results"][0]["status"] == "rejected", r.text
    assert sql("SELECT count(*) FROM operations")[0][0] == before
    assert sql("SELECT count(*) FROM operations WHERE label_photo_key IS NOT NULL")[0][0] == 0


def test_given_a_patch_with_a_foreign_label_id_or_raw_key_then_422(client, token_for, world):
    w = world
    r = _rest(client, token_for, w, "owner", w["farm_a"], w["a1"])
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    h = auth(token_for(w["owner"]))
    foreign = _label(client, token_for, w, "owner_b", w["farm_b"])
    assert client.patch(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=h, json={"label_photo_id": foreign}).status_code == 422
    assert client.patch(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=h, json={"label_photo_key": "farms/x/labels/y"}).status_code == 422


def test_given_an_export_body_with_a_file_key_or_url_then_422(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    ok = client.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=h, json=EXPORT)
    assert ok.status_code == 202, ok.text
    sql("UPDATE export_jobs SET state='done'")
    for extra in ({"file_keys": ["a"]}, {"file_key": "farms/x/exports/y/z.pdf"}, {"url": "https://evil.test/x"}):
        assert client.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=h, json={**EXPORT, **extra}).status_code == 422


def test_given_an_export_job_of_farm_b_requested_through_farm_a_then_404_and_no_signed_url(client, token_for, world):
    w = world
    hb = auth(token_for(w["owner_b"]))
    job = client.post(f"/v1/farms/{w['farm_b']}/registry/exports", headers=hb, json=EXPORT)
    assert job.status_code == 202, job.text
    jid = job.json()["id"]
    ha = auth(token_for(w["owner"]))
    r = client.get(f"/v1/farms/{w['farm_a']}/registry/exports/{jid}", headers=ha)
    assert r.status_code == 404 and "http" not in r.text and "X-Amz" not in r.text
    own = client.get(f"/v1/farms/{w['farm_b']}/registry/exports/{jid}", headers=hb)
    assert own.status_code == 200 and "file_keys" not in own.text


def test_given_responses_then_label_photo_key_and_file_keys_are_never_exposed(client, token_for, world):
    w = world
    lid = _label(client, token_for, w, "owner", w["farm_a"])
    created = _rest(client, token_for, w, "owner", w["farm_a"], w["a1"], label_photo_id=lid)
    assert created.status_code == 201, created.text
    h = auth(token_for(w["owner"]))
    for path in ("/operations", f"/operations/{created.json()['id']}"):
        assert "label_photo_key" not in client.get(f"/v1/farms/{w['farm_a']}{path}", headers=h).text


def test_given_an_unresolvable_ref_when_resolving_a_label_then_no_object_is_read(client, token_for, world, monkeypatch):
    w = world
    from app.operations import label

    reads = []
    monkeypatch.setattr(label, "read_object", lambda *a, **k: reads.append(a), raising=False)
    r = _rest(client, token_for, w, "owner", w["farm_a"], w["a1"], label_photo_id=str(uuid.uuid4()))
    assert r.status_code == 422 and not reads

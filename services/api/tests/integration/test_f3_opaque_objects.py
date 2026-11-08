"""T025 - G6: clients never name a storage key; ids are server-issued and scoped to (farm, user); signed URLs last 15 minutes."""
import io
import re
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f3 import (  # noqa: F401
    NOT_FOUND,
    call,
    seed_scene,
    seed_zone,
    sync_obs,
    sync_post,
    world3,
)

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512


def _photo(client, token_for, w, who, farm, zone):
    r = client.post(f"/v1/farms/{farm}/zones/{zone}/observations/photo", headers=auth(token_for(w[who])), files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()["photo_id"]


def _obs(client, token_for, w, who, farm, zone, channel, **extra):
    body = {"id": str(uuid.uuid4()), "note": "vu", **extra}
    if channel == "rest":
        return client.post(f"/v1/farms/{farm}/zones/{zone}/observations", headers=auth(token_for(w[who])), json=body)
    rid = body.pop("id")
    return sync_post(client, token_for(w[who]), [sync_obs(farm, zone, rid=rid, **{k: v for k, v in body.items() if k != "note"}, note=body["note"])])


def _ok(r, channel):
    return r.status_code == 201 if channel == "rest" else (r.status_code == 200 and r.json()["results"][0]["status"] == "applied")


def test_given_a_visible_scene_then_the_map_is_an_url_signed_for_15_minutes_resolved_from_the_scene_id(client, token_for, world3):
    w = world3
    scene, _mid = seed_scene(w["farm_a"], w["a1"])
    r = call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/vigor/scenes/{scene}/map")
    assert r.status_code == 200, r.text
    b = r.json()
    assert re.search(r"X-Amz-Expires=900\b", b["url"]) and b["acquired_on"] and b["expires_at"]
    assert "map_key" not in r.text and "farms/" not in r.text


def test_given_a_scene_of_another_farm_or_an_invisible_parcel_then_404_identical_and_no_url(client, token_for, world3):
    w = world3
    other, _ = seed_scene(w["farm_b"], w["b1"])
    hidden, _ = seed_scene(w["farm_a"], w["hidden"])
    mine, _ = seed_scene(w["farm_a"], w["a1"])
    f = f"/v1/farms/{w['farm_a']}/parcels"
    tok = token_for(w["worker"])
    assert call(client, tok, "GET", f"{f}/{w['a1']}/vigor/scenes/{mine}/map").status_code == 200
    unknown = call(client, tok, "GET", f"{f}/{w['a1']}/vigor/scenes/{uuid.uuid4()}/map")
    for path in (f"{w['a1']}/vigor/scenes/{other}/map", f"{w['hidden']}/vigor/scenes/{hidden}/map", f"{w['a1']}/vigor/scenes/{hidden}/map"):
        r = call(client, tok, "GET", f"{f}/{path}")
        assert r.status_code == 404 and r.json() == NOT_FOUND and r.text == unknown.text and "X-Amz" not in r.text, path


@pytest.mark.parametrize("channel", ["rest", "sync"])
def test_given_a_photo_id_issued_to_me_in_this_farm_then_it_is_consumed_once_and_stored_under_a_server_key(client, token_for, world3, channel):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    pid = _photo(client, token_for, w, "worker", w["farm_a"], z)
    r = _obs(client, token_for, w, "worker", w["farm_a"], z, channel, photo_id=pid)
    assert _ok(r, channel), r.text
    key = sql("SELECT photo_key FROM zone_observations WHERE zone_id=$1 AND photo_key IS NOT NULL", z)[0][0]
    assert re.fullmatch(rf"farms/{w['farm_a']}/zone-photos/[0-9a-f-]{{36}}", key)
    assert "farms/" not in r.text
    again = _obs(client, token_for, w, "worker", w["farm_a"], z, channel, photo_id=pid)
    assert not _ok(again, channel)


@pytest.mark.parametrize("channel", ["rest", "sync"])
def test_given_a_foreign_other_user_unknown_consumed_or_expired_photo_id_then_the_refusal_is_identical_and_nothing_is_written(client, token_for, world3, channel):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    zb = seed_zone(w["farm_b"], w["b1"])
    ok = _obs(client, token_for, w, "worker", w["farm_a"], z, channel, photo_id=_photo(client, token_for, w, "worker", w["farm_a"], z))
    assert _ok(ok, channel), ok.text
    foreign_farm = _photo(client, token_for, w, "owner_b", w["farm_b"], zb)
    sql("INSERT INTO worker_parcels (farm_id, user_id, parcel_id) VALUES ($1,$2,$3)", w["farm_a"], w["worker2"], w["a1"])  # decisions.md: worker2 must see the zone to deposit
    other_user = _photo(client, token_for, w, "worker2", w["farm_a"], z)
    expired = _photo(client, token_for, w, "worker", w["farm_a"], z)
    sql("UPDATE observation_uploads SET expires_at = now() - interval '1 minute' WHERE id=$1", uuid.UUID(expired))
    consumed = _photo(client, token_for, w, "worker", w["farm_a"], z)
    sql("UPDATE observation_uploads SET consumed_at = now() WHERE id=$1", uuid.UUID(consumed))
    before = sql("SELECT count(*) FROM zone_observations")[0][0]
    seen = set()
    for pid in (foreign_farm, other_user, str(uuid.uuid4()), expired, consumed):
        r = _obs(client, token_for, w, "worker", w["farm_a"], z, channel, photo_id=pid)
        if channel == "rest":
            assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_object_ref", r.text
            seen.add(r.text)
        else:
            res = r.json()["results"][0]
            assert r.status_code == 200 and res["status"] == "rejected" and res["error"]["code"] == "invalid_object_ref", r.text
            seen.add(str(res["error"]))
    assert len(seen) == 1, "responses must be identical (no oracle)"
    assert sql("SELECT count(*) FROM zone_observations")[0][0] == before


@pytest.mark.parametrize("channel", ["rest", "sync"])
@pytest.mark.parametrize("forged", [{"photo_key": "farms/x/zone-photos/y"}, {"map_key": "farms/x/vigor/y.png"}, {"raster_key": "r"},
                                    {"photo_key": "../etc/passwd"}, {"photo_id": "https://evil.test/x"}, {"url": "https://evil.test/x"}])
def test_given_a_raw_storage_key_or_url_in_a_body_then_it_is_refused_and_never_written(client, token_for, world3, channel, forged):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    assert _ok(_obs(client, token_for, w, "worker", w["farm_a"], z, channel), channel)
    before = sql("SELECT count(*) FROM zone_observations")[0][0]
    r = _obs(client, token_for, w, "worker", w["farm_a"], z, channel, **forged)
    if channel == "rest":
        assert r.status_code == 422, r.text
    else:
        assert r.status_code == 200 and r.json()["results"][0]["status"] == "rejected", r.text
    assert sql("SELECT count(*) FROM zone_observations")[0][0] == before
    assert sql("SELECT count(*) FROM zone_observations WHERE photo_key IS NOT NULL")[0][0] == 0


def test_given_a_photo_deposit_on_a_zone_of_another_farm_or_invisible_parcel_then_404_and_no_upload_row(client, token_for, world3):
    w = world3
    zb, zh = seed_zone(w["farm_b"], w["b1"]), seed_zone(w["farm_a"], w["hidden"])
    za = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["worker"])
    assert client.post(f"/v1/farms/{w['farm_a']}/zones/{za}/observations/photo", headers=auth(tok), files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")}).status_code == 201
    before = sql("SELECT count(*) FROM observation_uploads")[0][0]
    for z in (zb, zh):
        r = client.post(f"/v1/farms/{w['farm_a']}/zones/{z}/observations/photo", headers=auth(tok), files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")})
        assert r.status_code == 404 and r.json() == NOT_FOUND
    assert sql("SELECT count(*) FROM observation_uploads")[0][0] == before


def test_given_responses_then_no_storage_key_is_ever_exposed(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    _scene, _ = seed_scene(w["farm_a"], w["a1"])
    pid = _photo(client, token_for, w, "owner", w["farm_a"], z)
    assert client.post(f"/v1/farms/{w['farm_a']}/zones/{z}/observations", headers=auth(token_for(w["owner"])), json={"id": str(uuid.uuid4()), "note": "x", "photo_id": pid}).status_code == 201
    tok = token_for(w["owner"])
    for path in ("zones", "dashboard", f"parcels/{w['a1']}/vigor", f"parcels/{w['a1']}/vigor/compare", "alerts"):
        t = call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/{path}")
        assert t.status_code == 200 and not re.search(r"photo_key|map_key|raster_key|farms/[0-9a-f-]{36}/(vigor|zone-photos)", t.text), path

"""T022 - G4: caps are enforced before any costly work (gateway call, raster read, write); unbounded lists never exist."""
import io
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f3 import call, seed_scene, seed_zone, sync_obs, sync_post, world3  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512


@pytest.fixture
def spies(monkeypatch):
    """Spies on every costly collaborator: any call during a refusal is a failure."""
    from app.monitoring import gateways, rasters

    calls = []
    monkeypatch.setattr(gateways.WeatherGateway, "fetch", lambda *a, **k: calls.append("weather"), raising=True)
    monkeypatch.setattr(gateways.ImageryGateway, "scenes", lambda *a, **k: calls.append("imagery"), raising=True)
    monkeypatch.setattr(rasters, "read_raster", lambda *a, **k: calls.append("raster"), raising=True)
    return calls


def _f(w):
    return f"/v1/farms/{w['farm_a']}"


def test_given_a_valid_dashboard_request_then_200_and_limit_101_is_refused_without_work(client, token_for, world3, spies):
    w = world3
    tok = token_for(w["owner"])
    assert call(client, tok, "GET", f"{_f(w)}/dashboard?limit=100").status_code == 200
    assert call(client, tok, "GET", f"{_f(w)}/dashboard?limit=101").status_code == 422
    assert call(client, tok, "GET", f"{_f(w)}/dashboard?limit=0").status_code == 422
    assert spies == []


def test_given_the_default_page_then_at_most_50_parcels_are_returned(client, token_for, world3):
    w = world3
    assert len(call(client, token_for(w["owner"]), "GET", f"{_f(w)}/dashboard").json()["parcels"]) <= 50


def test_given_a_series_window_then_24_months_pass_and_longer_is_refused_without_reading_a_raster(client, token_for, world3, spies):
    w = world3
    tok = token_for(w["owner"])
    base = f"{_f(w)}/parcels/{w['a1']}/vigor"
    assert call(client, tok, "GET", f"{base}?from=2025-01-01&to=2026-12-31").status_code == 200
    assert call(client, tok, "GET", f"{base}?from=2024-01-01&to=2026-12-31").status_code == 422
    assert spies == []


def test_given_a_series_then_it_never_exceeds_400_points(client, token_for, world3):
    w = world3
    for i in range(405):
        _scene, _ = seed_scene(w["farm_a"], w["a1"], acquired_on=__import__("datetime").date.today() - __import__("datetime").timedelta(days=i % 700))
    body = call(client, token_for(w["owner"]), "GET", f"{_f(w)}/parcels/{w['a1']}/vigor?from=2025-01-01&to=2026-12-31")
    assert body.status_code == 200 and len(body.json()["points"]) <= 400


def test_given_the_weather_horizon_then_8_days_pass_and_any_other_horizon_is_refused_without_a_call(client, token_for, world3, spies):
    w = world3
    tok = token_for(w["owner"])
    assert call(client, tok, "GET", f"{_f(w)}/weather?days=8").status_code == 200
    for d in (7, 9, 30):
        assert call(client, tok, "GET", f"{_f(w)}/weather?days={d}").status_code == 422, d
    assert spies == []


def test_given_a_note_then_500_characters_pass_and_501_are_refused(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["owner"])
    url = f"{_f(w)}/zones/{z}/observations"
    assert call(client, tok, "POST", url, {"id": str(uuid.uuid4()), "note": "x" * 500}).status_code == 201
    assert call(client, tok, "POST", url, {"id": str(uuid.uuid4()), "note": "x" * 501}).status_code == 422
    assert sql("SELECT count(*) FROM zone_observations WHERE zone_id=$1", z)[0][0] == 1


def test_given_a_huge_body_then_413_from_the_declared_size_before_any_parsing(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["owner"])
    ok = call(client, tok, "POST", f"{_f(w)}/zones/{z}/observations", {"id": str(uuid.uuid4()), "note": "ok"})
    assert ok.status_code == 201
    body = ('{"note":"' + "x" * (2 * 1024 * 1024) + '"}').encode()
    r = client.post(f"{_f(w)}/zones/{z}/observations", headers={**auth(tok), "content-type": "application/json"}, content=body)
    assert r.status_code == 413, r.status_code  # size is read first: 413, not the 422 a parse would give


def test_given_a_photo_then_3_mb_pass_and_more_or_a_wrong_signature_is_refused(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["owner"])
    url = f"{_f(w)}/zones/{z}/observations/photo"
    ok = client.post(url, headers=auth(tok), files={"photo": ("a.jpg", io.BytesIO(JPEG), "image/jpeg")})
    assert ok.status_code == 201, ok.text
    big = JPEG + b"0" * (3 * 1024 * 1024)
    assert client.post(url, headers=auth(tok), files={"photo": ("a.jpg", io.BytesIO(big), "image/jpeg")}).status_code == 413
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 512
    assert client.post(url, headers=auth(tok), files={"photo": ("a.jpg", io.BytesIO(png), "image/jpeg")}).status_code in (400, 415, 422)
    assert client.post(url, headers=auth(tok), files={"photo": ("a.jpg", io.BytesIO(b"<?php evil ?>"), "image/jpeg")}).status_code in (400, 415, 422)


def test_given_a_sync_batch_of_101_operations_then_413_batch_too_large_before_any_write(client, token_for, world3, spies):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    tok = token_for(w["worker"])
    assert sync_post(client, tok, [sync_obs(w["farm_a"], z) for _ in range(100)]).status_code == 200
    before = sql("SELECT count(*) FROM zone_observations")[0][0]
    r = sync_post(client, tok, [sync_obs(w["farm_a"], z) for _ in range(101)])
    assert r.status_code == 413 and r.json()["detail"]["code"] == "batch_too_large"
    assert sql("SELECT count(*) FROM zone_observations")[0][0] == before
    assert spies == []

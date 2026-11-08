"""T026 - G4: caps are enforced before any costly work (balance computation, gateway call, write); reads never compute."""
import datetime as dt
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f4 import SYSTEM_BODY, TODAY4, call, sync_event, sync_post, world4  # noqa: F401


@pytest.fixture
def spies(monkeypatch):
    """Spies on every costly collaborator: any call during a refusal (or a read) is a failure."""
    from app.irrigation import plans, service
    from app.monitoring import gateways

    calls = []
    monkeypatch.setattr(plans, "compute_parcel_plan", lambda *a, **k: calls.append("balance"), raising=True)
    monkeypatch.setattr(service, "schedule_recompute", lambda *a, **k: calls.append("recompute"), raising=True)
    monkeypatch.setattr(gateways.WeatherGateway, "fetch", lambda *a, **k: calls.append("weather"), raising=True)
    monkeypatch.setattr(gateways.ObservedWeatherGateway, "fetch", lambda *a, **k: calls.append("observed"), raising=True)
    return calls


def _p(w, parcel=None):
    return f"/v1/farms/{w['farm_a']}/parcels/{parcel or w['a1']}"


def test_given_the_list_limit_then_100_passes_and_101_or_0_is_refused_without_work(client, token_for, world4, spies):
    w = world4
    tok, f = token_for(w["owner"]), f"/v1/farms/{w['farm_a']}"
    assert call(client, tok, "GET", f"{f}/irrigation/advice?limit=100").status_code == 200
    for bad in (101, 0):
        assert call(client, tok, "GET", f"{f}/irrigation/advice?limit={bad}").status_code == 422
        assert call(client, tok, "GET", f"{f}/irrigation/consumption?limit={bad}").status_code == 422
        assert call(client, tok, "GET", f"{_p(w)}/irrigation/events?limit={bad}").status_code == 422
    assert spies == []


def test_given_the_default_page_then_at_most_50_items_are_returned(client, token_for, world4):
    w = world4
    assert len(call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice").json()["items"]) <= 50


def test_given_a_balance_window_then_400_days_pass_and_more_is_refused_before_any_read(client, token_for, world4, spies):
    w = world4
    tok = token_for(w["owner"])
    to = TODAY4
    assert call(client, tok, "GET", f"{_p(w)}/irrigation/balance?from={to - dt.timedelta(days=399)}&to={to}").status_code == 200
    r = call(client, tok, "GET", f"{_p(w)}/irrigation/balance?from={to - dt.timedelta(days=400)}&to={to}")
    assert r.status_code == 422, r.text
    assert spies == []


def test_given_a_balance_then_it_never_exceeds_400_points(client, token_for, world4):
    from tests.integration._f4 import seed_balance

    w = world4
    for i in range(405):
        seed_balance(w["farm_a"], w["a1"], TODAY4 - dt.timedelta(days=i % 399 + 1) if i < 399 else TODAY4 - dt.timedelta(days=1 + i))
    r = call(client, token_for(w["owner"]), "GET", f"{_p(w)}/irrigation/balance?from={TODAY4 - dt.timedelta(days=399)}&to={TODAY4}")
    assert r.status_code == 200 and len(r.json()["days"]) <= 400


def test_given_a_consumption_window_then_24_months_pass_and_longer_is_refused_without_work(client, token_for, world4, spies):
    w = world4
    tok, f = token_for(w["owner"]), f"/v1/farms/{w['farm_a']}/irrigation/consumption"
    assert call(client, tok, "GET", f"{f}?from=2024-07-01&to=2026-06-04").status_code == 200
    assert call(client, tok, "GET", f"{f}?from=2024-01-01&to=2026-06-04").status_code == 422
    assert spies == []


@pytest.mark.parametrize("field,value", [
    ("performed_on", (TODAY4 - dt.timedelta(days=401)).isoformat()),     # backdating > 400 days
    ("performed_on", (TODAY4 + dt.timedelta(days=1)).isoformat()),       # future (injected clock)
    ("duration_min", 1441), ("duration_min", 0),
])
def test_given_an_invalid_event_field_then_422_without_balance_work_and_nothing_is_written(client, token_for, world4, spies, field, value):
    w = world4
    body = {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30, field: value}
    ok = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30})
    assert ok.status_code == 201, ok.text
    spies.clear()
    before = sql("SELECT count(*) FROM irrigation_events")[0][0]
    r = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/irrigation/events", body)
    assert r.status_code == 422 and spies == []
    assert sql("SELECT count(*) FROM irrigation_events")[0][0] == before


def test_given_a_backdating_of_exactly_400_days_then_it_is_accepted_with_the_injected_clock(client, token_for, world4):
    w = world4
    r = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": (TODAY4 - dt.timedelta(days=400)).isoformat(), "duration_min": 30})
    assert r.status_code == 201, r.text


def test_given_a_volume_above_the_surface_cap_then_422(client, token_for, world4, spies):
    w = world4
    assert call(client, token_for(w["owner"]), "POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "volume_m3": 1}).status_code == 201
    spies.clear()
    r = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "volume_m3": 10_000_000})
    assert r.status_code == 422 and spies == []


@pytest.mark.parametrize("body", [{**SYSTEM_BODY, "sectors_count": 51}, {**SYSTEM_BODY, "sectors_count": 0}, {**SYSTEM_BODY, "pump_flow_m3h": 0}, {**SYSTEM_BODY, "pump_flow_m3h": -1}])
def test_given_an_invalid_installation_then_422_and_no_version_is_written(client, token_for, world4, spies, body):
    w = world4
    assert call(client, token_for(w["owner"]), "PUT", f"{_p(w)}/irrigation-system", SYSTEM_BODY).status_code == 200
    n = sql("SELECT count(*) FROM irrigation_system_versions")[0][0]
    r = call(client, token_for(w["owner"]), "PUT", f"{_p(w)}/irrigation-system", body)
    assert r.status_code == 422 and spies == [] and sql("SELECT count(*) FROM irrigation_system_versions")[0][0] == n


@pytest.mark.parametrize("ec", [0, 100.1, -3])
def test_given_an_electrical_conductivity_out_of_range_then_422(client, token_for, world4, spies, ec):
    w = world4
    ok = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/water-analyses", {"id": str(uuid.uuid4()), "ec_ds_m": 100, "analysed_on": "2026-06-01"})
    assert ok.status_code == 201, ok.text
    r = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/water-analyses", {"id": str(uuid.uuid4()), "ec_ds_m": ec, "analysed_on": "2026-06-01"})
    assert r.status_code == 422 and spies == []


def test_given_a_huge_body_then_413_from_the_declared_size_before_any_parsing(client, token_for, world4, spies):
    w = world4
    tok = token_for(w["owner"])
    assert call(client, tok, "POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30}).status_code == 201
    body = ('{"note":"' + "x" * (2 * 1024 * 1024) + '"}').encode()
    r = client.post(f"{_p(w)}/irrigation/events", headers={**auth(tok), "content-type": "application/json"}, content=body)
    assert r.status_code == 413, r.status_code  # size read first: 413, not the 422 a parse would give
    assert spies.count("balance") == 0


def test_given_a_sync_batch_of_101_operations_then_413_batch_too_large_before_any_write(client, token_for, world4, spies):
    w = world4
    tok = token_for(w["worker"])
    assert sync_post(client, tok, [sync_event(w["farm_a"], w["a1"]) for _ in range(100)]).status_code == 200
    before = sql("SELECT count(*) FROM irrigation_events")[0][0]
    r = sync_post(client, tok, [sync_event(w["farm_a"], w["a1"]) for _ in range(101)])
    assert r.status_code == 413 and r.json()["detail"]["code"] == "batch_too_large"
    assert sql("SELECT count(*) FROM irrigation_events")[0][0] == before


def test_given_read_routes_then_they_only_read_the_cache_and_never_trigger_a_computation_or_a_gateway_call(client, token_for, world4, spies):
    w = world4
    tok, f = token_for(w["owner"]), f"/v1/farms/{w['farm_a']}"
    for path in ("irrigation/advice", f"parcels/{w['a1']}/irrigation/advice", f"parcels/{w['a1']}/irrigation/balance", "irrigation/consumption",
                 f"parcels/{w['a1']}/irrigation/events", f"parcels/{w['a1']}/irrigation-system", f"parcels/{w['a1']}/water-analyses"):
        assert call(client, tok, "GET", f"{f}/{path}").status_code == 200, path
    assert spies == []


def test_given_a_day_without_a_plan_then_the_advice_read_does_not_compute_one(client, token_for, world4, spies):
    w = world4
    p = w["p"][9]
    sql("UPDATE irrigation_plans SET for_date = for_date - 5 WHERE parcel_id=$1", p)
    r = call(client, token_for(w["owner"]), "GET", f"{_p(w, p)}/irrigation/advice")
    assert r.status_code == 200 and r.json()["is_last_known"] is True and spies == []

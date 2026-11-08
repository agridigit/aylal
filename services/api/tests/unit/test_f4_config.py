"""T010 - G5: F4 gateway configuration is empty by default; allow-list enforced at startup; no foreign SDK imported."""
import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO = pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
COMPOSE = REPO / "docker-compose.yml"
VARS = ("AYLAL_WEATHER_URL", "AYLAL_WEATHER_OBSERVED_URL")
KEYS = ("AYLAL_ENV", "AYLAL_JWT_SECRET", "AYLAL_OTP_PEPPER", "AYLAL_WEATHER_KEY", "AYLAL_WEATHER_OBSERVED_KEY", "AYLAL_EXTERNAL_ALLOWED_HOSTS") + VARS
STRONG = "s" * 40
FOREIGN = ("firebase", "firebase_admin", "pyfcm", "google", "onesignal", "apns", "twilio", "sentry_sdk", "mapbox", "openweather", "boto3_gcp", "meteomatics", "tomorrow")


def _env(monkeypatch, **values):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


@pytest.mark.parametrize("var", VARS)
def test_given_the_compose_file_then_f4_gateway_variables_default_to_empty_for_api_and_worker(var):
    text = COMPOSE.read_text(encoding="utf-8")
    found = re.findall(rf"{var}: \$\{{{var}:-([^}}]*)\}}", text)
    assert len(found) >= 2 and set(found) == {""}, f"{var}: {found}"


def test_given_the_repository_then_no_observed_weather_key_is_committed():
    for p in (COMPOSE, REPO / ".env.test"):
        if p.exists():
            for m in re.finditer(r"AYLAL_WEATHER_OBSERVED_KEY[:=]\s*(\S*)", p.read_text(encoding="utf-8")):
                assert m.group(1) in ("", '""', "${AYLAL_WEATHER_OBSERVED_KEY:-}")


def test_given_no_environment_then_the_observed_gateway_is_empty(monkeypatch):
    from app.config import get_settings

    _env(monkeypatch, AYLAL_ENV="dev")
    s = get_settings()
    assert (s.weather_url, s.weather_observed_url) == ("", "")


def test_given_prod_with_an_observed_url_outside_the_allowed_hosts_then_startup_is_refused(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         AYLAL_WEATHER_OBSERVED_URL="https://obs.example.ma/r", AYLAL_EXTERNAL_ALLOWED_HOSTS="meteo.example.ma")
    with pytest.raises(RuntimeError):
        validate_external_gateways(get_settings())


def test_given_prod_with_an_allowed_observed_url_or_none_then_validation_passes(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG)
    validate_external_gateways(get_settings())
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         AYLAL_WEATHER_OBSERVED_URL="https://obs.example.ma/r", AYLAL_EXTERNAL_ALLOWED_HOSTS="obs.example.ma")
    validate_external_gateways(get_settings())


def test_given_f4_sources_then_no_foreign_provider_sdk_is_imported_and_no_foreign_host_is_called():
    files = sorted((ROOT / "app" / "irrigation").glob("*.py")) + [ROOT / "app" / "sync" / "irrigation.py"]
    files += [ROOT / "app" / "routers" / f"{n}.py" for n in ("irrigation_systems", "irrigation_advice", "irrigation_events", "consumption", "water_analyses")]
    files += [REPO / "services/workers/tasks" / f"{n}.py" for n in ("compute_irrigation_plans", "send_irrigation_reminders", "import_irrigation_params")]
    assert any(p.name == "weather_input.py" for p in files), "app/irrigation/weather_input.py missing"
    allowed = ("localhost", "127.0.0.1", "example.test", "example.ma", "w3.org", "json-schema.org")
    for p in files:
        text = p.read_text(encoding="utf-8")
        for mod in re.findall(r"^\s*(?:from|import)\s+([A-Za-z0-9_]+)", text, flags=re.M):
            assert mod.lower() not in FOREIGN, f"{p.name} imports {mod}"
        for host in re.findall(r"https?://([A-Za-z0-9.-]+)", text):
            assert host.endswith(allowed) or host.startswith(allowed), f"{p.name} calls {host}"

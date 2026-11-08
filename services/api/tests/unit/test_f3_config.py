"""T009 - G5: external gateways are empty by default; non-Moroccan SDKs never imported by F3 code."""
import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO = pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
COMPOSE = REPO / "docker-compose.yml"
VARS = ("AYLAL_WEATHER_URL", "AYLAL_IMAGERY_URL", "AYLAL_PUSH_URL", "AYLAL_EXTERNAL_ALLOWED_HOSTS")
KEYS = ("AYLAL_ENV", "AYLAL_JWT_SECRET", "AYLAL_OTP_PEPPER", "AYLAL_WEATHER_KEY", "AYLAL_IMAGERY_KEY", "AYLAL_PUSH_KEY") + VARS
STRONG = "s" * 40
FOREIGN = ("firebase", "firebase_admin", "pyfcm", "fcm", "google", "onesignal", "apns", "twilio", "sentry_sdk", "mapbox", "openweather", "boto3_gcp")


def _env(monkeypatch, **values):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


@pytest.mark.parametrize("var", VARS)
def test_given_the_compose_file_then_f3_gateway_variables_default_to_empty(var):
    text = COMPOSE.read_text(encoding="utf-8")
    m = re.search(rf"{var}: \$\{{{var}:-([^}}]*)\}}", text)
    assert m is not None, f"{var} missing from docker-compose.yml"
    assert m.group(1) == ""


def test_given_the_repository_then_no_gateway_key_is_committed():
    for p in (COMPOSE, REPO / ".env.test"):
        if p.exists():
            for var in ("AYLAL_WEATHER_KEY", "AYLAL_IMAGERY_KEY", "AYLAL_PUSH_KEY"):
                for m in re.finditer(rf"{var}[:=]\s*(\S*)", p.read_text(encoding="utf-8")):
                    assert m.group(1) in ("", '""', f"${{{var}:-}}"), f"{var} has a value in {p.name}"


def test_given_no_environment_then_gateways_are_empty_and_no_host_is_allowed(monkeypatch):
    from app.config import get_settings

    _env(monkeypatch, AYLAL_ENV="dev")
    s = get_settings()
    assert (s.weather_url, s.imagery_url, s.push_url) == ("", "", "")
    assert tuple(s.external_allowed_hosts) == ()


def test_given_prod_with_a_url_outside_the_allowed_hosts_then_startup_is_refused(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         AYLAL_WEATHER_URL="https://meteo.example.ma/f", AYLAL_EXTERNAL_ALLOWED_HOSTS="autre.example.ma")
    with pytest.raises(RuntimeError):
        validate_external_gateways(get_settings())


def test_given_prod_with_an_empty_allow_list_and_a_url_then_startup_is_refused(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG, AYLAL_IMAGERY_URL="https://img.example.ma")
    with pytest.raises(RuntimeError):
        validate_external_gateways(get_settings())


def test_given_prod_with_a_plain_http_url_then_startup_is_refused(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         AYLAL_PUSH_URL="http://push.example.ma", AYLAL_EXTERNAL_ALLOWED_HOSTS="push.example.ma")
    with pytest.raises(RuntimeError):
        validate_external_gateways(get_settings())


def test_given_prod_with_allowed_https_urls_or_none_then_validation_passes(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG)
    validate_external_gateways(get_settings())
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         AYLAL_WEATHER_URL="https://meteo.example.ma/f", AYLAL_EXTERNAL_ALLOWED_HOSTS="meteo.example.ma")
    validate_external_gateways(get_settings())


def test_given_dev_with_an_unlisted_url_then_validation_does_not_refuse(monkeypatch):
    from app.config import get_settings, validate_external_gateways

    _env(monkeypatch, AYLAL_ENV="dev", AYLAL_WEATHER_URL="http://localhost:9/w")
    validate_external_gateways(get_settings())


def _f3_sources():
    files = [ROOT / "app" / "monitoring", ROOT / "app" / "sync" / "monitoring.py"]
    files += [ROOT / "app" / "routers" / f"{n}.py" for n in ("dashboard", "alerts", "vigor", "zones", "summary")]
    out = []
    for f in files:
        out += list(f.rglob("*.py")) if f.is_dir() else ([f] if f.exists() else [])
    return out


def test_given_f3_sources_then_no_foreign_provider_sdk_is_imported_and_no_foreign_host_is_called():
    sources = _f3_sources()
    assert any(p.name == "gateways.py" for p in sources), "F3 gateways module missing"
    allowed = ("localhost", "127.0.0.1", "example.test", "example.ma", "w3.org", "json-schema.org")
    for p in sources:
        text = p.read_text(encoding="utf-8")
        for mod in re.findall(r"^\s*(?:from|import)\s+([A-Za-z0-9_]+)", text, flags=re.M):
            assert mod.lower() not in FOREIGN, f"{p.name} imports {mod}"
        for host in re.findall(r"https?://([A-Za-z0-9.-]+)", text):
            assert host.endswith(allowed) or host.startswith(allowed), f"{p.name} calls {host}"

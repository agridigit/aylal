"""T008 - G4: no default secret, optional AI ports empty = unavailable, retention default, no foreign domain."""
import os
import pathlib
import re

import pytest

STRONG = "s" * 40
ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE = pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "docker-compose.yml"
KEYS = ("AYLAL_ENV", "AYLAL_JWT_SECRET", "AYLAL_OTP_PEPPER", "AYLAL_VISION_URL", "AYLAL_NLU_URL",
        "AYLAL_REGISTRY_RETENTION_YEARS", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD")


def _env(monkeypatch, **values):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def test_given_the_compose_file_then_f6_variables_default_to_empty():
    text = COMPOSE.read_text(encoding="utf-8")
    for var in ("AYLAL_VISION_URL", "AYLAL_NLU_URL"):
        m = re.search(rf"{var}: \$\{{{var}:-([^}}]*)\}}", text)
        assert m is not None, f"{var} missing from docker-compose.yml"
        assert m.group(1) == "", f"{var} has a non-empty default"


def test_given_prod_when_minio_credentials_are_missing_then_startup_is_refused(monkeypatch):
    from app.config import get_settings, require_minio_credentials

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG)
    with pytest.raises(RuntimeError):
        require_minio_credentials(get_settings())


def test_given_prod_when_minio_credentials_are_set_then_they_are_returned(monkeypatch):
    from app.config import get_settings, require_minio_credentials

    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         MINIO_ROOT_USER="u-real", MINIO_ROOT_PASSWORD="p-real-secret")
    assert require_minio_credentials(get_settings()) == ("u-real", "p-real-secret")


def test_given_ai_urls_unset_then_vision_and_nlu_are_unavailable(monkeypatch):
    from app.config import get_settings

    _env(monkeypatch, AYLAL_ENV="dev")
    s = get_settings()
    assert s.vision_url == "" and s.nlu_url == ""


def test_given_ai_urls_set_then_they_are_read_from_the_environment(monkeypatch):
    from app.config import get_settings

    _env(monkeypatch, AYLAL_ENV="dev", AYLAL_VISION_URL="http://vision.local", AYLAL_NLU_URL="http://nlu.local")
    s = get_settings()
    assert (s.vision_url, s.nlu_url) == ("http://vision.local", "http://nlu.local")


def test_given_no_override_then_registry_retention_is_five_years(monkeypatch):
    from app.config import get_settings

    _env(monkeypatch, AYLAL_ENV="dev")
    assert get_settings().registry_retention_years == 5


def test_given_f6_sources_then_no_foreign_domain_is_called():
    files = [ROOT / "app" / "operations", ROOT / "app" / "routers" / "operations.py",
             ROOT / "app" / "routers" / "phyto_products.py", ROOT / "app" / "routers" / "registry.py",
             ROOT / "app" / "sync" / "operations.py"]
    sources = []
    for f in files:
        sources += list(f.rglob("*.py")) if f.is_dir() else ([f] if f.exists() else [])
    assert any(p.name == "registry.py" and p.parent.name == "operations" for p in sources), "F6 registry module missing"
    allowed = ("localhost", "127.0.0.1", "example.test", "w3.org", "json-schema.org")
    for p in sources:
        for host in re.findall(r"https?://([A-Za-z0-9.-]+)", p.read_text(encoding="utf-8")):
            assert host.endswith(allowed) or host.startswith(allowed), f"{p.name} calls {host}"

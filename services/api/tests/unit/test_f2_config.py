"""T003 - tiles base URL comes from the environment only; startup refused outside dev/test without it."""
import pathlib

import pytest

from app.config import get_settings, require_tiles_base_url

STRONG = "s" * 40
KEYS = ("AYLAL_ENV", "AYLAL_JWT_SECRET", "AYLAL_OTP_PEPPER", "AYLAL_TILES_BASE_URL", "AYLAL_ENABLE_TEST_OTP")


def _env(monkeypatch, **values):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def test_given_prod_when_tiles_url_is_missing_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG)
    with pytest.raises(RuntimeError):
        require_tiles_base_url(get_settings())


def test_given_prod_when_tiles_url_is_set_then_it_is_read_from_env(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG,
         AYLAL_TILES_BASE_URL="https://tiles.example.test")
    assert require_tiles_base_url(get_settings()) == "https://tiles.example.test"


def test_given_dev_when_tiles_url_is_missing_then_it_is_empty(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="dev")
    assert require_tiles_base_url(get_settings()) == ""


def test_given_sources_then_no_hardcoded_tiles_or_minio_credentials():
    root = pathlib.Path(__file__).resolve().parents[2] / "app"
    text = "\n".join(p.read_text() for p in root.rglob("*.py"))
    for forbidden in ("minioadmin", "http://minio", "https://tiles.", "pmtiles.io"):
        assert forbidden not in text

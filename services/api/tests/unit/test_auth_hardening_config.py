"""Auth hardening: the API refuses to start with a weak JWT secret outside dev/test."""
import pytest

from app.config import get_settings

DEV_SECRET = "dev-only-secret-change-me"
STRONG = "s" * 40


def _env(monkeypatch: pytest.MonkeyPatch, **values: str | None) -> None:
    for key in ("AYLAL_ENV", "AYLAL_JWT_SECRET", "AYLAL_ENABLE_DEV_TOKEN", "AYLAL_OTP_PEPPER", "AYLAL_ENABLE_TEST_OTP"):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        if value is not None:
            monkeypatch.setenv(key, value)


def test_given_prod_env_when_secret_missing_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod")
    with pytest.raises(Exception):
        get_settings()


def test_given_prod_env_when_secret_shorter_than_32_chars_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET="x" * 31)
    with pytest.raises(Exception):
        get_settings()


def test_given_prod_env_when_secret_is_the_dev_value_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=DEV_SECRET)
    with pytest.raises(Exception):
        get_settings()


def test_given_env_absent_when_secret_is_weak_then_env_is_treated_as_prod_and_refused(monkeypatch):
    _env(monkeypatch, AYLAL_JWT_SECRET=DEV_SECRET)
    with pytest.raises(Exception):
        get_settings()


def test_given_env_absent_when_secret_is_strong_then_env_defaults_to_prod(monkeypatch):
    _env(monkeypatch, AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG)
    assert get_settings().env == "prod"


def test_given_prod_env_when_secret_is_strong_then_settings_load(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER=STRONG)
    assert get_settings().jwt_secret == STRONG


@pytest.mark.parametrize("env", ["dev", "test"])
def test_given_explicit_dev_or_test_env_when_secret_missing_then_settings_load(monkeypatch, env):
    _env(monkeypatch, AYLAL_ENV=env)
    assert get_settings().env == env


@pytest.mark.parametrize("env", ["staging", "production", ""])
def test_given_unknown_env_when_secret_is_weak_then_startup_is_refused(monkeypatch, env):
    _env(monkeypatch, AYLAL_ENV=env, AYLAL_JWT_SECRET=DEV_SECRET)
    with pytest.raises(Exception):
        get_settings()

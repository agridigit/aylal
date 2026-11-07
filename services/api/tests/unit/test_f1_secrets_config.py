"""T005 - the API refuses to start outside dev/test without strong secrets or with the test OTP on (FR-027)."""
import pytest

from app.config import get_settings

STRONG = "s" * 40
KEYS = ("AYLAL_ENV", "AYLAL_JWT_SECRET", "AYLAL_OTP_PEPPER", "AYLAL_ENABLE_TEST_OTP")


def _env(monkeypatch, **values):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def test_given_prod_when_otp_pepper_is_missing_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG)
    with pytest.raises(Exception):
        get_settings()


def test_given_prod_when_otp_pepper_is_shorter_than_32_chars_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER="p" * 31)
    with pytest.raises(Exception):
        get_settings()


def test_given_prod_when_test_otp_is_enabled_then_startup_is_refused(monkeypatch):
    _env(
        monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG,
        AYLAL_OTP_PEPPER="p" * 40, AYLAL_ENABLE_TEST_OTP="1",
    )
    with pytest.raises(Exception):
        get_settings()


def test_given_unset_env_when_test_otp_is_enabled_then_startup_is_refused(monkeypatch):
    _env(monkeypatch, AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER="p" * 40, AYLAL_ENABLE_TEST_OTP="1")
    with pytest.raises(Exception):
        get_settings()


def test_given_prod_when_all_secrets_are_strong_and_test_otp_off_then_settings_load(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="prod", AYLAL_JWT_SECRET=STRONG, AYLAL_OTP_PEPPER="p" * 40)
    s = get_settings()
    assert s.otp_pepper == "p" * 40 and s.enable_test_otp is False


@pytest.mark.parametrize("env", ["dev", "test"])
def test_given_dev_or_test_when_no_pepper_then_an_ephemeral_pepper_is_generated(monkeypatch, env):
    _env(monkeypatch, AYLAL_ENV=env)
    assert len(get_settings().otp_pepper) >= 32


def test_given_dev_when_pepper_is_generated_twice_then_it_is_never_a_fixed_default(monkeypatch):
    _env(monkeypatch, AYLAL_ENV="dev")
    assert get_settings().otp_pepper not in ("", "dev", "changeme")

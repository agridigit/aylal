"""Runtime settings read from the environment (no external default host)."""
import os
import secrets
from dataclasses import dataclass

_WEAK_SECRET = "dev-only-secret-change-me"
_MIN_SECRET_LEN = 32
_LOCAL_ENVS = ("dev", "test")
# Per-process fallback for dev/test only; never a fixed, guessable value.
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)
_EPHEMERAL_PEPPER = secrets.token_urlsafe(48)


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    env: str
    jwt_secret: str
    otp_pepper: str
    sms_gateway_url: str
    sms_gateway_key: str
    enable_test_otp: bool
    trusted_proxies: tuple[str, ...] = ()
    tiles_base_url: str = ""


def get_settings() -> Settings:
    env = os.environ.get("AYLAL_ENV", "prod")
    secret = os.environ.get("AYLAL_JWT_SECRET")
    if env in _LOCAL_ENVS:
        secret = secret or _EPHEMERAL_SECRET
    elif not secret or len(secret) < _MIN_SECRET_LEN or secret == _WEAK_SECRET:
        raise RuntimeError(
            f"AYLAL_JWT_SECRET must be set to at least {_MIN_SECRET_LEN} chars "
            "(and not the dev value) when AYLAL_ENV is not dev/test"
        )
    pepper = os.environ.get("AYLAL_OTP_PEPPER", "")
    if env in _LOCAL_ENVS:
        pepper = pepper or _EPHEMERAL_PEPPER
    elif len(pepper) < _MIN_SECRET_LEN:
        raise RuntimeError(
            f"AYLAL_OTP_PEPPER must be set to at least {_MIN_SECRET_LEN} chars "
            "when AYLAL_ENV is not dev/test"
        )
    enable_test_otp = os.environ.get("AYLAL_ENABLE_TEST_OTP", "0") == "1"
    if enable_test_otp and env not in _LOCAL_ENVS:
        raise RuntimeError("AYLAL_ENABLE_TEST_OTP=1 is forbidden when AYLAL_ENV is not dev/test")
    tiles_base_url = os.environ.get("AYLAL_TILES_BASE_URL", "").strip()
    return Settings(
        database_url=os.environ.get(
            "AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal"
        ),
        redis_url=os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"),
        env=env,
        jwt_secret=secret,
        otp_pepper=pepper,
        sms_gateway_url=os.environ.get("AYLAL_SMS_GATEWAY_URL", ""),
        sms_gateway_key=os.environ.get("AYLAL_SMS_GATEWAY_KEY", ""),
        enable_test_otp=enable_test_otp,
        tiles_base_url=tiles_base_url,
        trusted_proxies=tuple(
            p.strip() for p in os.environ.get("AYLAL_TRUSTED_PROXIES", "").split(",") if p.strip()
        ),
    )


def require_tiles_base_url(settings: Settings) -> str:
    """Tiles URL for the map endpoints; refused outside dev/test when absent (guard-rail 5)."""
    if settings.env not in _LOCAL_ENVS and not settings.tiles_base_url:
        raise RuntimeError("AYLAL_TILES_BASE_URL must be set when AYLAL_ENV is not dev/test")
    return settings.tiles_base_url

"""Runtime settings read from the environment (no external default host)."""
import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlparse

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
    # F6: optional AI ports (empty = unavailable, the caller falls back to manual entry)
    vision_url: str = ""
    nlu_url: str = ""
    registry_retention_years: int = 5
    minio_user: str = ""
    minio_password: str = ""
    # F3: external gateways hosted in Morocco. Empty = "unavailable" (no default value, no call); only listed hosts are called.
    weather_url: str = ""
    imagery_url: str = ""
    push_url: str = ""
    weather_key: str = ""
    # F4: optional observed-rain gateway (empty = unavailable: the past day then uses the last forecast, confidence lowered)
    weather_observed_url: str = ""
    weather_observed_key: str = ""
    imagery_key: str = ""
    push_key: str = ""
    external_allowed_hosts: tuple[str, ...] = ()
    # F8: optional receipt OCR and market-price gateways (empty = unavailable, no call, no invented value)
    ocr_url: str = ""
    market_prices_url: str = ""


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
        vision_url=os.environ.get("AYLAL_VISION_URL", "").strip(),
        nlu_url=os.environ.get("AYLAL_NLU_URL", "").strip(),
        registry_retention_years=int(os.environ.get("AYLAL_REGISTRY_RETENTION_YEARS", "5") or "5"),
        minio_user=os.environ.get("MINIO_ROOT_USER", ""),
        minio_password=os.environ.get("MINIO_ROOT_PASSWORD", ""),
        weather_url=os.environ.get("AYLAL_WEATHER_URL", "").strip(),
        imagery_url=os.environ.get("AYLAL_IMAGERY_URL", "").strip(),
        push_url=os.environ.get("AYLAL_PUSH_URL", "").strip(),
        weather_key=os.environ.get("AYLAL_WEATHER_KEY", ""),
        weather_observed_url=os.environ.get("AYLAL_WEATHER_OBSERVED_URL", "").strip(),
        weather_observed_key=os.environ.get("AYLAL_WEATHER_OBSERVED_KEY", ""),
        imagery_key=os.environ.get("AYLAL_IMAGERY_KEY", ""),
        push_key=os.environ.get("AYLAL_PUSH_KEY", ""),
        external_allowed_hosts=tuple(
            h.strip().lower() for h in os.environ.get("AYLAL_EXTERNAL_ALLOWED_HOSTS", "").split(",") if h.strip()
        ),
        ocr_url=os.environ.get("AYLAL_OCR_URL", "").strip(),
        market_prices_url=os.environ.get("AYLAL_MARKET_PRICES_URL", "").strip(),
        trusted_proxies=tuple(
            p.strip() for p in os.environ.get("AYLAL_TRUSTED_PROXIES", "").split(",") if p.strip()
        ),
    )


def require_tiles_base_url(settings: Settings) -> str:
    """Tiles URL for the map endpoints; refused outside dev/test when absent (guard-rail 5)."""
    if settings.env not in _LOCAL_ENVS and not settings.tiles_base_url:
        raise RuntimeError("AYLAL_TILES_BASE_URL must be set when AYLAL_ENV is not dev/test")
    return settings.tiles_base_url


def require_minio_credentials(settings: Settings) -> tuple[str, str]:
    """Object-storage credentials; refused outside dev/test when absent (no default secret)."""
    if settings.env not in _LOCAL_ENVS and not (settings.minio_user and settings.minio_password):
        raise RuntimeError("MINIO_ROOT_USER and MINIO_ROOT_PASSWORD must be set when AYLAL_ENV is not dev/test")
    return settings.minio_user, settings.minio_password


def validate_external_gateways(settings: Settings) -> None:
    """Outside dev/test a gateway URL must be HTTPS and its host listed in AYLAL_EXTERNAL_ALLOWED_HOSTS (G5)."""
    if settings.env in _LOCAL_ENVS:
        return
    for name, url in (
        ("WEATHER", settings.weather_url), ("WEATHER_OBSERVED", settings.weather_observed_url),
        ("IMAGERY", settings.imagery_url), ("PUSH", settings.push_url),
        ("OCR", settings.ocr_url), ("MARKET_PRICES", settings.market_prices_url),
    ):
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise RuntimeError(f"AYLAL_{name}_URL must use HTTPS when AYLAL_ENV is not dev/test")
        if (parsed.hostname or "").lower() not in settings.external_allowed_hosts:
            raise RuntimeError(f"AYLAL_{name}_URL host must be listed in AYLAL_EXTERNAL_ALLOWED_HOSTS")

"""Runtime settings read from the environment (no external default host)."""
import os
import secrets
from dataclasses import dataclass

_WEAK_SECRET = "dev-only-secret-change-me"
_MIN_SECRET_LEN = 32
_LOCAL_ENVS = ("dev", "test")
# Per-process fallback for dev/test only; never a fixed, guessable value.
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    env: str
    jwt_secret: str


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
    return Settings(
        database_url=os.environ.get(
            "AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal"
        ),
        redis_url=os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"),
        env=env,
        jwt_secret=secret,
    )

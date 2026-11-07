"""Runtime settings read from the environment (no external default host)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    env: str
    jwt_secret: str = "dev-only-secret-change-me"


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal"
        ),
        redis_url=os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"),
        env=os.environ.get("AYLAL_ENV", "dev"),
        jwt_secret=os.environ.get("AYLAL_JWT_SECRET", "dev-only-secret-change-me"),
    )

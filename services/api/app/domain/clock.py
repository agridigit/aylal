"""F4 injected clock (G7), mirror of packages/domain/src/clock.ts. The only system-time read is annotated `clock-allow`."""
import datetime as dt
from collections.abc import Callable
from typing import Protocol
from zoneinfo import ZoneInfo

FARM_TZ = ZoneInfo("Africa/Casablanca")


class Clock(Protocol):
    def now(self) -> dt.datetime: ...


def _aware(t: dt.datetime) -> dt.datetime:
    if t.tzinfo is None:
        raise ValueError("a clock instant must be timezone-aware")
    return t


class FixedClock:
    def __init__(self, t: dt.datetime) -> None:
        self._t = _aware(t)

    def now(self) -> dt.datetime:
        return self._t


class AdvancingClock(FixedClock):
    def advance(self, delta: dt.timedelta) -> None:
        self._t = self._t + delta


class _SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)  # clock-allow


_SYSTEM = _SystemClock()


def system_clock() -> Clock:
    return _SYSTEM


def get_clock() -> Clock:
    """FastAPI dependency; tests override it through `app.dependency_overrides[get_clock]`."""
    return _SYSTEM


def instant(clock: Clock) -> dt.datetime:
    """The single place that asks an injected clock for the time."""
    return clock.now()  # clock-allow


def local_day(t: dt.datetime, tz: ZoneInfo = FARM_TZ) -> dt.date:
    return _aware(t).astimezone(tz).date()


def local_hour(t: dt.datetime, tz: ZoneInfo = FARM_TZ) -> int:
    return _aware(t).astimezone(tz).hour


def is_before_local_hour(t: dt.datetime, hour: int, tz: ZoneInfo = FARM_TZ) -> bool:
    return local_hour(t, tz) < hour


ClockFactory = Callable[[], Clock]

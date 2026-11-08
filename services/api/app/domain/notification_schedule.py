"""Frost notification schedule (SC-003), mirror of packages/domain/src/notification-schedule.ts.

Morocco keeps a permanent UTC+1 offset for this rule (the notification hour is local).
"""
import datetime as dt

MOROCCO = dt.timezone(dt.timedelta(hours=1))
LATEST_HOUR = 18


def frost_notify_at(forecast_day: str, first_seen_at: dt.datetime, notify_hour: int) -> tuple[dt.datetime, bool]:
    """Evening before at `notify_hour` (capped at 18:00 local); seen later: immediate, `late` after 18:00."""
    eve = dt.date.fromisoformat(forecast_day) - dt.timedelta(days=1)
    target = dt.datetime.combine(eve, dt.time(min(notify_hour, LATEST_HOUR)), tzinfo=MOROCCO)
    if first_seen_at <= target:
        return target.astimezone(dt.UTC), False
    latest = dt.datetime.combine(eve, dt.time(LATEST_HOUR), tzinfo=MOROCCO)
    return first_seen_at, first_seen_at > latest

"""F2 basic field/season rules (pure). Mirrors packages/domain; shared vectors come with T009."""
import datetime as dt

NAME_MAX = 80
ARCHIVE_RETENTION_DAYS = 90
MIN_VERTICES, MAX_VERTICES = 3, 500
IRRIGATIONS = ("rainfed", "gravity", "sprinkler", "drip", "pivot")
SOURCES = ("draw_taps", "draw_gps", "import")
BLOCK_KINDS = ("block", "irrigation_sector")
CYCLES = ("perennial", "annual")


def valid_name(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value.strip()) <= NAME_MAX


def purge_after(archived_at: dt.datetime) -> dt.datetime:
    return archived_at + dt.timedelta(days=ARCHIVE_RETENTION_DAYS)


def season_dates_error(
    cycle: str, planting_year: int | None, sowing_date: dt.date | None,
    started_at: dt.date, ended_at: dt.date | None,
) -> str | None:
    """Return the offending field name, or None when the dates are coherent."""
    if planting_year is not None and sowing_date is not None:
        return "sowing_date"
    if planting_year is not None and (cycle != "perennial" or not 1900 <= planting_year <= dt.date.today().year + 1):
        return "planting_year"
    if sowing_date is not None and cycle != "annual":
        return "sowing_date"
    if ended_at is not None and ended_at < started_at:
        return "ended_at"
    return None

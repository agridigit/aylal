"""F6 caps (G3), mirror of packages/domain/src/operation-limits.ts (shared vectors f6_limits.json)."""
import datetime as dt
from decimal import Decimal

LIMITS: dict[str, int] = {
    "page_default": 50,
    "page_limit": 200,
    "batch": 100,
    "parcels": 50,
    "product_lines": 5,
    "note_length": 500,
    "free_product_length": 80,
    "operator_length": 80,
    "text_length": 500,
    "export_rows": 10_000,
    "export_years": 5,
    "ops_per_farm_year": 20_000,
    "planned_count": 500,
    "label_bytes": 3 * 1024 * 1024,
    "body_bytes": 256 * 1024,
}
DOSE_MIN, DOSE_MAX, DOSE_DECIMALS = Decimal("0.001"), Decimal("100000"), 3
MIN_PERFORMED_ON = dt.date(2000, 1, 1)
MAX_FUTURE_YEARS = 2

_MAX_COUNT = {
    "product_lines", "batch", "note_length", "free_product_length", "operator_length",
    "export_rows", "export_years", "ops_per_farm_year", "planned_count",
}


def latest_performed_on(today: dt.date) -> dt.date:
    """Today plus two years (29 February falls back to 28)."""
    year = today.year + MAX_FUTURE_YEARS
    try:
        return today.replace(year=year)
    except ValueError:
        return today.replace(year=year, day=28)


def valid_dose(value: float | Decimal) -> bool:
    dose = Decimal(str(value))
    return DOSE_MIN <= dose <= DOSE_MAX and dose == dose.quantize(Decimal(1).scaleb(-DOSE_DECIMALS))


def within_limit(rule: str, value: float | str, today: dt.date) -> bool:
    """True when `value` respects the cap named `rule`; an unknown rule is refused."""
    if rule == "performed_on":
        if not isinstance(value, str):
            return False
        try:
            day = dt.date.fromisoformat(value)
        except ValueError:
            return False
        return MIN_PERFORMED_ON <= day <= latest_performed_on(today)
    if isinstance(value, str) or isinstance(value, bool):
        return False
    if rule == "parcels":
        return 1 <= value <= LIMITS["parcels"]
    if rule == "page_limit":
        return 1 <= value <= LIMITS["page_limit"]
    if rule == "dose":
        return valid_dose(value)
    return rule in _MAX_COUNT and 0 <= value <= LIMITS[rule]

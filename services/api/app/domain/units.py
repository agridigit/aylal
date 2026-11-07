"""Dose unit conversion, mirror of units.ts."""
from decimal import Decimal

DOSE_UNITS = ("L/ha", "mL/ha", "kg/ha", "g/ha")
_FACTOR = {
    ("L/ha", "mL/ha"): Decimal(1000), ("mL/ha", "L/ha"): Decimal("0.001"),
    ("kg/ha", "g/ha"): Decimal(1000), ("g/ha", "kg/ha"): Decimal("0.001"),
}


def convert_dose(value: float | Decimal, source: str, target: str) -> Decimal | None:
    """Convert between compatible units; None when they are not convertible."""
    number = Decimal(str(value))
    if source == target:
        return number
    factor = _FACTOR.get((source, target))
    return None if factor is None else number * factor

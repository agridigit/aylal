"""Moroccan mobile number normalisation, mirror of packages/domain/src/phone.ts."""
import re

_LOCAL = re.compile(r"0([67]\d{8})")
_INTL = re.compile(r"\+212([67]\d{8})")


def normalize_phone(value: str) -> str | None:
    compact = re.sub(r"[\s-]", "", value)
    if compact.startswith("00212"):
        compact = "+" + compact[2:]
    m = _LOCAL.fullmatch(compact) or _INTL.fullmatch(compact)
    return f"+212{m.group(1)}" if m else None

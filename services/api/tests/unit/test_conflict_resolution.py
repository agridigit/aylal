"""Python replica of packages/domain conflict resolution replays the shared vectors (R6, AC3.4)."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTORS = json.loads((DOMAIN_DIR / "vectors/conflict.field_merge.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: v["name"])
def test_python_resolution_gives_the_same_result_as_the_typescript_vectors(v: dict) -> None:
    from app.domain.conflict import resolve_field_conflicts

    out = resolve_field_conflicts(v["record"], v["op"])
    for key in ("fields", "field_versions", "server_version", "has_conflict", "conflicts"):
        assert out[key] == v["expect"][key]


def test_given_skewed_device_clocks_then_resolution_is_identical() -> None:
    from app.domain.conflict import resolve_field_conflicts

    v = next(x for x in VECTORS if "last arrival" in x["name"])
    a = resolve_field_conflicts(v["record"], {**v["op"], "device_clock": "1970-01-01T00:00:00Z"})
    b = resolve_field_conflicts(v["record"], {**v["op"], "device_clock": "2099-01-01T00:00:00Z"})
    assert a == b

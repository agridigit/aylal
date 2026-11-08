"""Shared helpers of the F4 unit tests: shared TS/Python vectors (vectors/f4_*.json) and subset matching."""
import importlib
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def load(name):
    raw = json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))
    return raw["cases"] if isinstance(raw, dict) else raw


def matches(actual, expected, tol=0.01, exact=False, path="$"):
    """`expected` is a subset of `actual` (numbers within `tol`) unless `exact` (same key set, recursively)."""
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"
    elif isinstance(expected, (int, float)):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), f"{path}: {actual!r} is not a number"
        assert abs(actual - expected) <= tol, f"{path}: {actual} vs {expected}"
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{path}: {actual!r} != {expected!r}"
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            matches(a, e, tol, exact, f"{path}[{i}]")
    else:
        assert isinstance(actual, dict), f"{path}: not an object"
        if exact:
            assert sorted(actual) == sorted(expected), f"{path}: keys {sorted(actual)} != {sorted(expected)}"
        for k, e in expected.items():
            matches(actual.get(k), e, tol, exact, f"{path}.{k}")


def vector_params(file, fns=None):
    return [pytest.param(v, id=v["name"]) for v in load(file) if fns is None or v["fn"] in fns]


def run(v, module):
    """Call `module.<fn>(input)` (single dict argument, dict result) and compare with the shared expectation."""
    mod = importlib.import_module(module)
    fn = getattr(mod, v["fn"])
    matches(fn(json.loads(json.dumps(v["input"]))), v["expected"], v.get("tol", 0.01), v.get("exact", False))

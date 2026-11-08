"""Shared helpers of the F8 unit tests: shared TS/Python vectors (vectors/f8_*.json); modules are imported inside the tests so a missing rule
fails by ModuleNotFoundError/AttributeError (feature absent), never at collection."""
import importlib
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def load(name):
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))


def matches(actual, expected, exact=False, path="$"):
    if expected is None or isinstance(expected, (bool, str, int, float)):
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{path}: {actual!r} != {expected!r}"
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            matches(a, e, exact, f"{path}[{i}]")
    else:
        assert isinstance(actual, dict), f"{path}: not an object"
        if exact:
            assert sorted(actual) == sorted(expected), f"{path}: keys {sorted(actual)} != {sorted(expected)}"
        for k, e in expected.items():
            matches(actual.get(k), e, exact, f"{path}.{k}")


def vector_params(file):
    return [pytest.param(v, id=v["name"]) for v in load(file)]


def run(v, module):
    fn = getattr(importlib.import_module(module), v["fn"])
    matches(fn(json.loads(json.dumps(v["input"]))), v["expected"], v.get("exact", False))

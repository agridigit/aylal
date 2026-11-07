import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _load(name: str) -> list[dict]:
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))


VECTORS = _load("trial_record.json") + _load("parcel.json")


def _key(errors: list[dict]) -> list[tuple[str, str]]:
    return sorted((e["field"], e["code"]) for e in errors)


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: f"{v['rule']}: {v['name']}")
def test_generated_models_give_same_verdict_as_ts_vectors(vector: dict) -> None:
    from app.generated.validation import validate

    verdict = validate(vector["rule"], vector["input"])
    assert verdict["valid"] is vector["expect"]["valid"]
    assert _key(verdict["errors"]) == _key(vector["expect"]["errors"])

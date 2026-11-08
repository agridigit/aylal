"""Validation of live F3 responses against specs/006-dashboard-monitoring/contracts/openapi.yaml components."""
import os
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
SPEC = yaml.safe_load((REPO / "specs/006-dashboard-monitoring/contracts/openapi.yaml").read_text(encoding="utf-8"))


def errors(component: str, body) -> list[str]:
    schema = {"$ref": f"#/components/schemas/{component}", "components": SPEC["components"]}
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in Draft202012Validator(schema).iter_errors(body)]


def assert_valid(component: str, body) -> None:
    assert errors(component, body) == [], errors(component, body)

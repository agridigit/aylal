"""Loader of specs/005-operations-journal/contracts/openapi.yaml for the F6 contract tests."""
import os
from pathlib import Path

import yaml

SPEC = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "specs/005-operations-journal/contracts/openapi.yaml"
DOC = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
PATHS = DOC["paths"]
SCHEMAS = DOC["components"]["schemas"]


def codes(path: str, method: str) -> set[str]:
    return set(PATHS[path][method]["responses"])

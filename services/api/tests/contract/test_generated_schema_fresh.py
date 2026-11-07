import json
import os
import subprocess
from pathlib import Path

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
GENERATED = Path(__file__).resolve().parents[2] / "app" / "generated"


def test_generated_json_schemas_match_zod_export() -> None:
    exported = sorted((DOMAIN_DIR / "schema").glob("*.json"))
    assert exported, "Zod export produced no JSON Schema in packages/domain/schema"
    for src in exported:
        copy = GENERATED / "schema" / src.name
        assert copy.exists(), f"missing generated schema {copy}"
        assert json.loads(copy.read_text()) == json.loads(src.read_text()), f"stale: {src.name}"


def test_generated_pydantic_models_are_up_to_date() -> None:
    assert (GENERATED / "models.py").exists(), "generated Pydantic models missing"
    result = subprocess.run(
        ["python", "-m", "app.generated.check_fresh"], capture_output=True, text=True, cwd=GENERATED.parents[1]
    )
    assert result.returncode == 0, result.stdout + result.stderr

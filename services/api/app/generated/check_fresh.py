"""Regenerate Pydantic models from the JSON Schemas and compare with models.py.

`python -m app.generated.check_fresh`          exit 1 when models.py is stale.
`python -m app.generated.check_fresh --write`  rewrite models.py.
"""

import difflib
import json
import sys
import tempfile
from pathlib import Path

from datamodel_code_generator import DataModelType, InputFileType, generate

HERE = Path(__file__).resolve().parent
SCHEMA_DIR = HERE / "schema"
MODELS = HERE / "models.py"


def _bundle() -> str:
    defs: dict[str, object] = {}
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema.pop("$schema", None)
        defs[schema["title"]] = schema
    return json.dumps({"title": "Bundle", "type": "object", "properties": {}, "$defs": defs})


def render() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "models.py"
        generate(
            _bundle(),
            input_file_type=InputFileType.JsonSchema,
            output=out,
            output_model_type=DataModelType.PydanticV2BaseModel,
            disable_timestamp=True,
        )
        return out.read_text(encoding="utf-8")


def main(argv: list[str]) -> int:
    expected = render()
    if "--write" in argv:
        MODELS.write_text(expected, encoding="utf-8")
        return 0
    current = MODELS.read_text(encoding="utf-8") if MODELS.exists() else ""
    if current == expected:
        return 0
    sys.stdout.write("".join(difflib.unified_diff(current.splitlines(True), expected.splitlines(True))))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Import of the agronomic referentials (Kc per stage, root depth, depletion fraction, soil reserves, salinity, rain method...).

Nothing agronomic ships with the application: the tables stay empty until a file validated by agronomy is imported here.
`validated_by` and `source` are MANDATORY (in the file or as arguments); a file without them is refused and nothing is written.
"""
import json
from pathlib import Path
from typing import Any

from monitoring_db import dsn

_CROP_FIELDS = ("kc", "root_depth_m", "depletion_fraction", "ece_threshold_ds_m", "ece_max_ds_m")


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is mandatory")
    return value.strip()


async def import_irrigation_params(ctx: dict[str, Any], path: str | None = None, data: dict[str, Any] | None = None,
                                   validated_by: str | None = None, source: str | None = None) -> dict[str, int]:
    import asyncpg

    payload = data if data is not None else json.loads(Path(_required(path, "path")).read_text(encoding="utf-8"))
    by = _required(validated_by or payload.get("validated_by"), "validated_by")
    src = _required(source or payload.get("source"), "source")
    counts = {"crops": 0, "soils": 0, "params": 0}
    conn = await asyncpg.connect(dsn())
    try:
        async with conn.transaction():
            for row in payload.get("crops", []):
                await conn.execute(
                    "INSERT INTO crop_irrigation_params (crop_slug, stage_key, kc, root_depth_m, depletion_fraction, ece_threshold_ds_m, ece_max_ds_m,"
                    " validated, validated_by, source, imported_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, $11)"
                    " ON CONFLICT (crop_slug, stage_key) DO UPDATE SET kc = $3, root_depth_m = $4, depletion_fraction = $5, ece_threshold_ds_m = $6,"
                    " ece_max_ds_m = $7, validated = $8, validated_by = $9, source = $10, imported_at = $11",
                    row["crop_slug"], row["stage_key"], *(row.get(f) for f in _CROP_FIELDS), bool(row.get("validated", True)), by, src,
                    _stamp(ctx, payload),
                )
                counts["crops"] += 1
            for row in payload.get("soils", []):
                await conn.execute(
                    "INSERT INTO soil_textures (texture_key, available_water_mm_per_m, validated_by, source) VALUES ($1,$2,$3,$4)"
                    " ON CONFLICT (texture_key) DO UPDATE SET available_water_mm_per_m = $2, validated_by = $3, source = $4",
                    row["texture_key"], row.get("available_water_mm_per_m"), by, src,
                )
                counts["soils"] += 1
            for key, value in payload.get("params", {}).items():
                await conn.execute(
                    "INSERT INTO irrigation_params (key, value, validated_by, source) VALUES ($1, $2::jsonb, $3, $4)"
                    " ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, validated_by = $3, source = $4",
                    key, json.dumps(value), by, src,
                )
                counts["params"] += 1
    finally:
        await conn.close()
    return counts


def _stamp(ctx: dict[str, Any], payload: dict[str, Any]) -> Any:
    from clock import instant
    from irrigation_db import clock_for

    return instant(clock_for(payload.get("imported_at"), ctx.get("clock")))

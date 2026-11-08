"""Import of the weather thresholds per crop and stage from a file validated by agronomy (never invented here).

The file path comes from AYLAL_CROP_THRESHOLDS_FILE (JSON list). A row without `source` and `validated_by` is skipped.
"""
import json
import os
from typing import Any

from monitoring_db import dsn

_NUMBERS = ("chergui_tmax_c", "chergui_rh_max_pct", "chergui_wind_kmh", "heavy_rain_mm_24h", "strong_wind_kmh")


async def import_crop_thresholds(ctx: dict[str, Any], path: str | None = None) -> dict[str, int]:
    import asyncpg

    source = path or os.environ.get("AYLAL_CROP_THRESHOLDS_FILE", "")
    if not source:
        return {"imported": 0, "skipped": 0}
    with open(source, encoding="utf-8") as fh:
        rows = json.load(fh)
    imported = skipped = 0
    conn = await asyncpg.connect(dsn())
    try:
        async with conn.transaction():
            for r in rows:
                if not (r.get("source") and r.get("validated_by")) or r.get("source") == "fixture" or any(r.get(k) is None for k in _NUMBERS):
                    skipped += 1
                    continue
                await conn.execute(
                    "INSERT INTO crop_weather_thresholds (crop_slug, stage_key, frost_c, chergui_tmax_c, chergui_rh_max_pct,"
                    " chergui_wind_kmh, heavy_rain_mm_24h, strong_wind_kmh, source, validated_by, validated_at)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,now())"
                    " ON CONFLICT (crop_slug, stage_key) DO UPDATE SET frost_c = $3, chergui_tmax_c = $4, chergui_rh_max_pct = $5,"
                    " chergui_wind_kmh = $6, heavy_rain_mm_24h = $7, strong_wind_kmh = $8, source = $9, validated_by = $10, validated_at = now()",
                    r["crop_slug"], r["stage_key"], r.get("frost_c"), *(r[k] for k in _NUMBERS), r["source"], r["validated_by"],
                )
                imported += 1
    finally:
        await conn.close()
    return {"imported": imported, "skipped": skipped}

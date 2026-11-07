"""F2 season, crop and phenology rules (pure). Mirror of packages/domain/src/{season,phenology}.ts."""
import datetime as dt


def can_start_season(active, crop_id: str) -> str:
    return "season_already_active" if any(s["crop_id"] == crop_id for s in active) else "ok"


def season_date(crop: dict, inp: dict, today: str) -> dict:
    year, sowing = inp.get("planting_year"), inp.get("sowing_date")
    if year is not None and sowing is not None:
        return {"ok": False, "code": "both_dates_forbidden"}
    if year is None and sowing is None:
        return {"ok": False, "code": "date_required"}
    if crop["cycle"] == "perennial":
        if year is None:
            return {"ok": False, "code": "wrong_date_kind"}
        if isinstance(year, int) and 1900 <= year <= int(today[:4]) + 1:
            return {"ok": True}
        return {"ok": False, "code": "planting_year_out_of_range"}
    if sowing is None:
        return {"ok": False, "code": "wrong_date_kind"}
    try:
        dt.date.fromisoformat(sowing)
    except ValueError:
        return {"ok": False, "code": "sowing_date_invalid"}
    return {"ok": True}


def estimate_stage(crop: dict, season: dict, today: str, gdd: float | None = None) -> dict:
    stages = sorted(crop.get("stages") or [], key=lambda s: s["gdd_from"])
    if not stages:
        return {"stage": None, "approximate": False}
    approximate = gdd is None
    if gdd is not None:
        value = gdd
    else:
        if not season.get("sowing_date"):
            return {"stage": None, "approximate": False}
        value = (dt.date.fromisoformat(today) - dt.date.fromisoformat(season["sowing_date"])).days
    if value < 0:
        return {"stage": None, "approximate": approximate}
    current = stages[0]
    for s in stages:
        if value >= s["gdd_from"]:
            current = s
    return {"stage": current["key"], "approximate": approximate}


def display_stage(season: dict):
    return season.get("stage_corrected") or season.get("stage_estimated")


def reestimate_stage(crop: dict, season: dict, today: str, gdd: float | None = None) -> dict:
    """Recompute the estimate only; the farmer's correction is never touched."""
    return {**season, "stage_estimated": estimate_stage(crop, season, today, gdd)["stage"]}


def advice_enabled(crop: dict) -> bool:
    """Advice needs validated agronomy and stages; free crops have none."""
    return crop.get("has_agronomy") is True and bool(crop.get("stages"))

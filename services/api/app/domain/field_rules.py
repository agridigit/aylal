"""F2 field rules (pure). Mirror of packages/domain/src/{field,merge}.ts."""
from app.domain.geometry import area_ha, centroid, is_in_morocco, rings_touch, validate_ring

LIMITS = {"MIN_VERTICES": 3, "MAX_VERTICES": 500, "MAX_AREA_HA": 5000, "MAX_FIELDS_PER_FARM": 500, "MAX_NAME_LENGTH": 80}
IMAGERY_MIN_AREA_HA = 0.3
IRRIGATION_MODES = ("rainfed", "gravity", "sprinkler", "drip", "pivot")


def can_create_field(current_count: int) -> dict:
    if current_count < LIMITS["MAX_FIELDS_PER_FARM"]:
        return {"ok": True}
    return {"ok": False, "code": "field_limit_reached"}


def imagery_suitable(area: float, under_greenhouse: bool) -> bool:
    return area >= IMAGERY_MIN_AREA_HA and not under_greenhouse


def validate_field(inp: dict) -> dict:
    name = inp.get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not 1 <= len(name) <= LIMITS["MAX_NAME_LENGTH"]:
        return {"ok": False, "code": "name_invalid"}
    r = validate_ring(inp["ring"])
    if not r["ok"]:
        return r
    if not is_in_morocco(centroid(r["ring"])):
        return {"ok": False, "code": "outside_morocco"}
    ha = area_ha(r["ring"])
    if ha > LIMITS["MAX_AREA_HA"]:
        return {"ok": False, "code": "area_too_large"}
    declared = inp.get("area_declared_ha")
    if declared is not None and not declared > 0:
        return {"ok": False, "code": "area_declared_invalid"}
    irrigation = inp.get("irrigation")
    if irrigation is not None and irrigation not in IRRIGATION_MODES:
        return {"ok": False, "code": "irrigation_invalid"}
    greenhouse = inp.get("greenhouse")
    if greenhouse is not None and not isinstance(greenhouse, bool):
        return {"ok": False, "code": "greenhouse_invalid"}
    return {
        "ok": True, "ring": r["ring"], "area_ha": ha, "area_declared_ha": declared,
        "irrigation": irrigation, "greenhouse": bool(greenhouse),
    }


def merge_fields(survivor: dict, others: list, seasons: list) -> dict:
    if not others:
        return {"ok": False, "code": "merge_needs_two_fields"}
    allf = [survivor, *others]
    seen, queue = {0}, [0]
    while queue:
        i = queue.pop(0)
        for j, f in enumerate(allf):
            if j not in seen and rings_touch(allf[i]["ring"], f["ring"]):
                seen.add(j)
                queue.append(j)
    if len(seen) != len(allf):
        return {"ok": False, "code": "merge_not_contiguous"}
    ids = {f["id"] for f in allf}
    mine = [s for s in seasons if s["field_id"] in ids]
    by_crop: dict[str, list] = {}
    for s in mine:
        if s["ended_at"] is None:
            by_crop.setdefault(s["crop_id"], []).append(s)
    dropped: set[str] = set()
    for group in by_crop.values():
        for s in sorted(group, key=lambda s: (s["started_at"], s["id"]))[1:]:
            dropped.add(s["id"])
    return {
        "ok": True,
        "area_ha": sum(area_ha(f["ring"]) for f in allf),
        "kept_season_ids": [s["id"] for s in mine if s["id"] not in dropped],
        "dropped_season_ids": sorted(dropped),
    }

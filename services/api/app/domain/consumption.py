"""R4: consumption summary, mirror of consumption.ts. Aggregate only: no author, no note."""
from typing import Any


def summarise_consumption(i: dict[str, Any]) -> dict[str, Any]:
    parcels = []
    for p in i["parcels"]:
        area = p.get("area_ha")
        ratio = p["volume_m3"] / area if isinstance(area, (int, float)) and area > 0 else None
        parcels.append({"parcel_id": p["parcel_id"], "volume_m3": p["volume_m3"], "volume_m3_per_ha": ratio})
    total = sum(p["volume_m3"] for p in parcels)
    return {"parcels": parcels, "total_m3": total, "empty": total == 0}

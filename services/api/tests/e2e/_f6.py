"""Shared helpers for the F6 e2e tests (stack through the TLS proxy; catalogue rows are seeded in the stack database)."""
import datetime as dt
import json
import uuid

import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square, unique_phone  # noqa: F401
from tests.helpers import sql

TODAY = dt.date.today()


def field_with_crop(c: httpx.Client, h: dict, farm: str, name: str, lon: float, slug: str = "olive") -> tuple[str, str]:
    crops = {x["slug"]: x for x in c.get("/crops", headers=h).json()["items"]}
    f = c.post(f"/farms/{farm}/fields", json={"name": name, "geometry": square(lon)}, headers=h).json()
    s = c.post(f"/farms/{farm}/fields/{f['id']}/seasons", json={"crop_id": crops[slug]["id"], "started_at": "2026-01-01", **({"planting_year": 2015} if slug == "olive" else {"sowing_date": "2026-01-01"})}, headers=h)
    assert s.status_code == 201, s.text
    return f["id"], s.json()["id"]


def product(name: str, uses: list[dict]) -> uuid.UUID:
    """A catalogue product with uses in the stack database; name carries a random suffix so reruns do not collide."""
    version, pid = uuid.uuid4(), uuid.uuid4()
    sql("INSERT INTO catalog_versions (id, imported_at, source_date, row_count, checksum) VALUES ($1, now(), current_date, 1, 'e2e')", version)
    sql("INSERT INTO phyto_products (id, name, name_normalized, active_ingredients, catalog_version_id) VALUES ($1,$2,$3,$4::jsonb,$5)",
        pid, name, name.lower(), json.dumps([{"name": "cuivre", "concentration": "50%"}]), version)
    for u in uses:
        sql("INSERT INTO phyto_product_uses (id, product_id, crop_slug, max_dose, dose_unit, dar_days, max_applications) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            uuid.uuid4(), pid, u["crop_slug"], u.get("max_dose"), u.get("dose_unit", "L/ha"), u.get("dar_days"), u.get("max_applications"))
    return pid


def body(parcels, **kw) -> dict:
    return {"id": str(uuid.uuid4()), "type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": list(parcels), **kw}

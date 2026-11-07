"""Catalogue fixtures for F6 phyto tests (real PostgreSQL): versions, products, authorised uses, crops, seasons."""
import datetime as dt
import json
import uuid

from tests.helpers import sql
from tests.integration._f2 import add_season


def crops(n: int = 2) -> list[tuple[uuid.UUID, str]]:
    """The first n reference crops as (id, slug); slugs come from the seeded reference, never guessed."""
    rows = sql("SELECT id, slug FROM crops WHERE farm_id IS NULL ORDER BY slug LIMIT $1", n)
    assert len(rows) == n
    return [(r["id"], r["slug"]) for r in rows]


def grow(farm, field, crop_id):
    """Start an open campaign (season) of `crop_id` on the parcel; returns the season id."""
    return add_season(farm, field, crop_id)


def add_catalog(source_date: dt.date | None = None) -> uuid.UUID:
    vid = uuid.uuid4()
    sql("INSERT INTO catalog_versions (id, imported_at, source_date, row_count, checksum) VALUES ($1, now(), $2, 1, 'x')",
        vid, source_date or dt.date(2026, 10, 1))
    return vid


def add_product(version, name, uses=(), *, ingredients=None, expired=False):
    """A catalogue product with its authorised uses: dicts of crop_slug, max_dose, dose_unit, dar_days, max_applications."""
    pid = uuid.uuid4()
    sql("INSERT INTO phyto_products (id, name, name_normalized, registration_no, holder, active_ingredients, expired_at,"
        " catalog_version_id) VALUES ($1,$2,$3,'R-1','Holder',$4::jsonb,$5,$6)",
        pid, name, name.lower(), json.dumps(ingredients or [{"name": "cuivre", "concentration": "50%"}]),
        dt.datetime.now(dt.UTC) if expired else None, version)
    for use in uses:
        sql("INSERT INTO phyto_product_uses (id, product_id, crop_slug, max_dose, dose_unit, dar_days, max_applications)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7)", uuid.uuid4(), pid, use["crop_slug"], use.get("max_dose"),
            use.get("dose_unit", "L/ha"), use.get("dar_days"), use.get("max_applications"))
    return pid


def codes(warnings):
    return [w["code"] for w in warnings]

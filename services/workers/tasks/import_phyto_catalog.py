"""Monthly import of the phyto homologation catalogue, hosted in Morocco (local file or the stack's object store).

Source (port): `async fetch() -> bytes`, a gzip JSON {source_date, products: [{name, registration_no, holder,
homologation_expires_on, active_ingredients, uses: [...]}]}. Default: AYLAL_PHYTO_CATALOG_SOURCE = `file://...` or
`s3://bucket/key`; empty = nothing is imported; any other scheme (http, https, ftp) is refused with no connection.
Limits are checked before parsing (3 MB compressed, 50 MB decompressed). The import is atomic and the same file never
creates a second version; previous versions are kept (frozen registry snapshots point at them).
"""
import asyncio
import datetime as dt
import hashlib
import json
import os
import uuid
import zlib
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

import asyncpg

MAX_COMPRESSED = 3 * 1024 * 1024
MAX_DECOMPRESSED = 50 * 1024 * 1024
MAX_NAME = 200


class Source(Protocol):
    async def fetch(self) -> bytes: ...


class FileSource:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    async def fetch(self) -> bytes:
        size = self.path.stat().st_size
        if size > MAX_COMPRESSED:
            raise ValueError("catalog_too_large")
        return await asyncio.to_thread(self.path.read_bytes)


class ObjectSource:
    def __init__(self, bucket: str, key: str) -> None:
        self.bucket, self.key = bucket, key

    async def fetch(self) -> bytes:
        from tasks.object_storage import get_storage

        client = get_storage().client

        def read() -> bytes:
            data: bytes = client.get_object(Bucket=self.bucket, Key=self.key)["Body"].read(MAX_COMPRESSED + 1)
            return data

        return await asyncio.to_thread(read)


def source_from_env() -> Source | None:
    raw = os.environ.get("AYLAL_PHYTO_CATALOG_SOURCE", "").strip()
    if not raw:
        return None
    url = urlparse(raw)
    if url.scheme == "file":
        return FileSource(unquote(url.path))
    if url.scheme == "s3" and url.netloc and url.path.strip("/"):
        return ObjectSource(url.netloc, url.path.lstrip("/"))
    raise ValueError("catalog_source: only file:// and s3:// (hosted with the stack) are accepted")


def _unpack(data: bytes) -> Any:
    if len(data) > MAX_COMPRESSED:
        raise ValueError("catalog_too_large")
    inflater = zlib.decompressobj(wbits=31)
    try:
        raw = inflater.decompress(data, MAX_DECOMPRESSED + 1)
    except zlib.error as e:
        raise ValueError("catalog_invalid: not gzip") from e
    if len(raw) > MAX_DECOMPRESSED or inflater.unconsumed_tail:
        raise ValueError("catalog_too_large")
    try:
        return json.loads(raw)
    except ValueError as e:
        raise ValueError("catalog_invalid: not json") from e


def _date(value: Any, field: str) -> dt.date | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as e:
        raise ValueError(f"catalog_invalid: {field}") from e


def _int(value: Any, field: str, minimum: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"catalog_invalid: {field}")
    return value


def _text(value: Any, field: str, limit: int, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > limit:
        raise ValueError(f"catalog_invalid: {field}")
    return value


def _validate(doc: Any) -> tuple[dt.date, list[dict[str, Any]]]:
    if not isinstance(doc, dict) or not isinstance(doc.get("products"), list):
        raise ValueError("catalog_invalid: products")
    source_date = _date(doc.get("source_date"), "source_date")
    if source_date is None:
        raise ValueError("catalog_invalid: source_date")
    products: list[dict[str, Any]] = []
    for p in doc["products"]:
        if not isinstance(p, dict):
            raise ValueError("catalog_invalid: product")
        ingredients = p.get("active_ingredients") or []
        uses = p.get("uses") or []
        if not isinstance(ingredients, list) or not isinstance(uses, list):
            raise ValueError("catalog_invalid: lists")
        clean_uses = []
        for u in uses:
            if not isinstance(u, dict):
                raise ValueError("catalog_invalid: use")
            dose = u.get("max_dose")
            if dose is not None and (isinstance(dose, bool) or not isinstance(dose, (int, float)) or dose <= 0):
                raise ValueError("catalog_invalid: max_dose")
            clean_uses.append({
                "crop_slug": _text(u.get("crop_slug"), "crop_slug", 80, required=True), "target": _text(u.get("target"), "target", 200),
                "max_dose": dose, "dose_unit": _text(u.get("dose_unit"), "dose_unit", 20),
                "dar_days": _int(u.get("dar_days"), "dar_days", 0), "max_applications": _int(u.get("max_applications"), "max_applications", 1),
                "interval_days": _int(u.get("interval_days"), "interval_days", 0),
            })
        name = _text(p.get("name"), "name", MAX_NAME, required=True)
        assert name is not None
        products.append({
            "name": name, "registration_no": _text(p.get("registration_no"), "registration_no", 80),
            "holder": _text(p.get("holder"), "holder", 200), "expires": _date(p.get("homologation_expires_on"), "homologation_expires_on"),
            "ingredients": ingredients, "uses": clean_uses,
        })
    return source_date, products


async def import_phyto_catalog(ctx: dict[str, Any]) -> str | None:
    source: Source | None = ctx.get("source") or source_from_env()
    if source is None:
        return None
    data = await source.fetch()
    source_date, products = _validate(_unpack(data))
    checksum = hashlib.sha256(data).hexdigest()
    dsn = os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('import_phyto_catalog'))")
            if await conn.fetchval("SELECT 1 FROM catalog_versions WHERE checksum = $1", checksum):
                return None
            version = uuid.uuid4()
            now = dt.datetime.now(dt.UTC)
            await conn.execute(
                "INSERT INTO catalog_versions (id, imported_at, source_date, row_count, checksum) VALUES ($1,$2,$3,$4,$5)",
                version, now, source_date, len(products), checksum)
            for p in products:
                pid = uuid.uuid4()
                expired = now if p["expires"] is not None and p["expires"] < now.date() else None
                await conn.execute(
                    "INSERT INTO phyto_products (id, name, name_normalized, registration_no, holder, active_ingredients,"
                    " homologation_expires_on, expired_at, catalog_version_id) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9)",
                    pid, p["name"], p["name"].strip().lower(), p["registration_no"], p["holder"], json.dumps(p["ingredients"]),
                    p["expires"], expired, version)
                if p["uses"]:
                    await conn.executemany(
                        "INSERT INTO phyto_product_uses (id, product_id, crop_slug, target, max_dose, dose_unit, dar_days,"
                        " max_applications, interval_days) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                        [(uuid.uuid4(), pid, u["crop_slug"], u["target"], u["max_dose"], u["dose_unit"], u["dar_days"],
                          u["max_applications"], u["interval_days"]) for u in p["uses"]])
        return str(version)
    finally:
        await conn.close()

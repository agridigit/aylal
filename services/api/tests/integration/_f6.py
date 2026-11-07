"""Shared F6 fixtures/helpers for integration tests (real PostgreSQL, no mocks)."""
import datetime as dt
import uuid

import pytest

from tests.helpers import auth, op, sql
from tests.integration._f2 import add_field, assign, new_user  # noqa: F401  (re-exported)

TODAY = dt.date.today()
ROLES = ("owner", "manager", "worker")


def op_body(parcels, **kw):
    body = {"id": str(uuid.uuid4()), "type": "irrigation", "performed_on": TODAY.isoformat(),
            "parcel_ids": [str(p) for p in parcels]}
    body.update(kw)
    return body


def add_operation(farm, author, parcel, *, status="validated", type_="irrigation", performed_on=None):
    """Insert an operation and its read-model line directly (fixture only)."""
    oid = uuid.uuid4()
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) VALUES ($1,$2,$3,$4,$5,$6)",
        oid, farm, type_, performed_on or TODAY, status, author)
    sql("INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, author_id, type, performed_on, status) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)", uuid.uuid4(), farm, oid, parcel, author, type_, performed_on or TODAY, status)
    return oid


def add_registry(farm, operation, parcel, *, performed_on=None, kind="application", operator_user=None, **extra):
    rid = uuid.uuid4()
    cols = dict(id=rid, farm_id=farm, operation_id=operation, parcel_id=parcel, entry_kind=kind,
                performed_on=performed_on or TODAY, parcel_name="P", crop_name="Tomate", area_ha=1,
                product_name="Prod", is_free_product=False, dose=1, dose_unit="L/ha", allocated_quantity=1,
                operator_name="Op", operator_user_id=operator_user, warnings="[]", recorded_by=operator_user or uuid.uuid4(),
                retain_until=(performed_on or TODAY) + dt.timedelta(days=365 * 5))
    cols.update(extra)
    names = ", ".join(cols)
    marks = ", ".join(f"${i + 1}" + ("::jsonb" if k == "warnings" else "") for i, k in enumerate(cols))
    sql(f"INSERT INTO registry_entries ({names}) VALUES ({marks})", *cols.values())
    return rid


@pytest.fixture
def world(make_farm):
    owner, manager, worker, owner_b, outsider = (new_user() for _ in range(5))
    farm_a = make_farm({owner: "owner", manager: "manager", worker: "worker"})
    farm_b = make_farm({owner_b: "owner"})
    a1, a2, b1 = add_field(farm_a, "A1"), add_field(farm_a, "A2", lon=-7.55), add_field(farm_b, "B1", lon=-7.5)
    assign(farm_a, worker, a1)
    return dict(owner=owner, manager=manager, worker=worker, owner_b=owner_b, outsider=outsider,
                farm_a=farm_a, farm_b=farm_b, a1=a1, a2=a2, b1=b1)


def routes(farm, operation, field, job):
    """Every F6 farm route as (method, path, json body) addressed on `farm`."""
    f = f"/v1/farms/{farm}"
    return [
        ("GET", f"{f}/operations", None),
        ("POST", f"{f}/operations", op_body([field])),
        ("GET", f"{f}/operations/{operation}", None),
        ("PATCH", f"{f}/operations/{operation}", {"note": "x"}),
        ("POST", f"{f}/operations/{operation}/done", None),
        ("POST", f"{f}/operations/{operation}/cancel", None),
        ("POST", f"{f}/operations/{operation}/reschedule", {"performed_on": (TODAY + dt.timedelta(days=3)).isoformat()}),
        ("POST", f"{f}/operations/{operation}/validate", None),
        ("GET", f"{f}/operations/{operation}/corrections", None),
        ("POST", f"{f}/operations/check", op_body([field])),
        ("POST", f"{f}/operations/parse", {"text": "irrigation"}),
        ("POST", f"{f}/operations/label", None),
        ("POST", f"{f}/phyto-products/free", {"name": "Maison"}),
        ("GET", f"{f}/fields/{field}/earliest-harvest", None),
        ("GET", f"{f}/registry", None),
        ("POST", f"{f}/registry/exports", {"period_from": "2026-01-01", "period_to": "2026-12-31", "format": "pdf", "scope": "farm", "lang": "fr"}),
        ("GET", f"{f}/registry/exports/{job}", None),
    ]


def call(client, token, method, path, body):
    return client.request(method, path, headers=auth(token), json=body)


def sync_op(table, farm, rid, fields, kind="put"):
    o = op(farm, rid, kind=kind, fields=fields)
    o["table"] = table
    return o

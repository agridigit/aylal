"""T013 - G6: F8 schemas are extra=forbid; no storage key, URL, foreign farm_id or derived amount from a client; storage keys are server-named."""
import re
import uuid

import pytest
from pydantic import ValidationError

PARCEL, ITEM = str(uuid.uuid4()), str(uuid.uuid4())
BODIES = {
    "ExpenseInput": {"id": str(uuid.uuid4()), "category": "fuel", "amount_cents": 12500, "spent_on": "2026-06-03", "allocation_mode": "general"},
    "HarvestInput": {"id": str(uuid.uuid4()), "parcel_id": PARCEL, "quantity_milli": 1000, "unit": "kg", "harvested_on": "2026-06-03"},
    "SaleInput": {"id": str(uuid.uuid4()), "parcel_id": PARCEL, "quantity_milli": 1000, "unit_price_cents": 500, "buyer": "Ali", "sold_on": "2026-06-03"},
    "StockPurchaseInput": {"id": str(uuid.uuid4()), "stock_item_id": ITEM, "qty_milli": 1000, "unit_price_cents": 200, "moved_on": "2026-06-03"},
    "StockAdjustmentInput": {"id": str(uuid.uuid4()), "stock_item_id": ITEM, "counted_milli": 900, "reason": "inventory", "moved_on": "2026-06-03"},
}
SERVER_FIELDS = [{"file_key": "farms/x/y"}, {"object_key": "k"}, {"url": "https://evil.test/x"}, {"author_id": str(uuid.uuid4())},
                 {"farm_id": str(uuid.uuid4())}, {"share_cents": 5}, {"total_cents": 5}, {"unit_cost_cents": 5}, {"server_version": 9},
                 {"parcel_archived_at": "2026-01-01T00:00:00Z"}, {"kind": "reversal"}, {"reverses_id": str(uuid.uuid4())}]


@pytest.mark.parametrize("extra", SERVER_FIELDS, ids=lambda e: next(iter(e)))
@pytest.mark.parametrize("name", sorted(BODIES))
def test_given_a_storage_key_url_or_server_field_in_a_body_then_it_is_refused(name, extra):
    from app.economics import schemas

    model = getattr(schemas, name)
    model.model_validate(BODIES[name])
    with pytest.raises(ValidationError):
        model.model_validate({**BODIES[name], **extra})


def test_given_a_farm_and_a_receipt_then_the_storage_key_is_server_named_uuid_under_the_farm_prefix():
    from app.economics.receipts import new_object_key

    farm = uuid.uuid4()
    k1, k2 = new_object_key(farm, "image/jpeg"), new_object_key(farm, "image/jpeg")
    assert k1 != k2
    assert re.fullmatch(rf"farms/{farm}/receipts/[0-9a-f]{{8}}-[0-9a-f]{{4}}-4[0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}", k1), k1

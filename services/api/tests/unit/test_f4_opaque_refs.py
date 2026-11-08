"""T015 - G6: F4 schemas are extra=forbid; no storage key, URL or server field from a client; operation_id is a server uuid5."""
import uuid

import pytest
from pydantic import ValidationError

EVENT = {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30}
SYSTEM = {"kind": "drip", "sectors_count": 2, "pump_flow_m3h": 10}
ANALYSIS = {"id": str(uuid.uuid4()), "ec_ds_m": 2.1, "analysed_on": "2026-06-01"}
SERVER_FIELDS = [{"file_key": "farms/x/y"}, {"object_key": "k"}, {"url": "https://evil.test/x"}, {"operation_id": str(uuid.uuid4())},
                 {"author_id": str(uuid.uuid4())}, {"net_mm_applied": 3}, {"net_mm": 3}, {"parcel_archived_at": "2026-01-01T00:00:00Z"},
                 {"server_version": 9}, {"farm_id": str(uuid.uuid4())}, {"status": "cancelled"}]


def _models():
    from app.irrigation import schemas

    return [("event", schemas.IrrigationEventInput, EVENT), ("system", schemas.IrrigationSystemInput, SYSTEM), ("analysis", schemas.WaterAnalysisInput, ANALYSIS)]


@pytest.mark.parametrize("extra", SERVER_FIELDS, ids=lambda e: next(iter(e)))
@pytest.mark.parametrize("idx", [0, 1, 2])
def test_given_a_storage_key_url_or_server_field_in_a_body_then_it_is_refused(idx, extra):
    _, model, ok = _models()[idx]
    model.model_validate(ok)
    with pytest.raises(ValidationError):
        model.model_validate({**ok, **extra})


def test_given_a_derived_volume_with_a_duration_then_it_is_refused_as_both_modes_at_once():
    from app.irrigation.schemas import IrrigationEventInput

    IrrigationEventInput.model_validate({**EVENT})
    with pytest.raises(ValidationError):
        IrrigationEventInput.model_validate({**EVENT, "volume_m3": 12})


def test_given_a_farm_and_an_event_then_the_operation_id_is_a_deterministic_uuid5_of_farm_and_event():
    from app.irrigation.ids import NS_F4, operation_id_for

    farm, ev = uuid.uuid4(), uuid.uuid4()
    assert operation_id_for(farm, ev) == uuid.uuid5(NS_F4, f"{farm}:{ev}") == operation_id_for(farm, ev)
    assert operation_id_for(uuid.uuid4(), ev) != operation_id_for(farm, ev)

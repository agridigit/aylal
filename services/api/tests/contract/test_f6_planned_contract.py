"""T061 - done, cancel, validate and reschedule of planned operations conform to the contract."""
import datetime as dt

from tests.contract._f6_spec import PATHS, codes
from tests.helpers import auth
from tests.integration._f6 import TODAY, add_operation, world  # noqa: F401

BASE = "/v1/farms/{farm_id}/operations/{operation_id}"


def test_given_the_contract_then_done_cancel_and_reschedule_are_documented_with_their_error_codes():
    assert "200" in codes(BASE + "/done", "post") and "200" in codes(BASE + "/cancel", "post")
    assert {"200", "403", "404", "409", "422"} <= codes(BASE + "/reschedule", "post")
    body = PATHS[BASE + "/reschedule"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["required"] == ["performed_on"] and body["additionalProperties"] is False


def test_given_a_planned_operation_then_done_cancel_and_reschedule_return_the_documented_status_codes(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    future = TODAY + dt.timedelta(days=2)
    a = add_operation(w["farm_a"], w["owner"], w["a1"], status="planned", performed_on=future)
    b = add_operation(w["farm_a"], w["owner"], w["a1"], status="planned", performed_on=future)
    c = add_operation(w["farm_a"], w["owner"], w["a1"], status="planned", performed_on=future)
    base = f"/v1/farms/{w['farm_a']}/operations"
    moved = client.post(f"{base}/{a}/reschedule", headers=h, json={"performed_on": (future + dt.timedelta(days=1)).isoformat()})
    assert moved.status_code == 200 and moved.json()["status"] == "planned"
    assert client.post(f"{base}/{b}/done", headers=h).json()["status"] == "validated"
    assert client.post(f"{base}/{c}/cancel", headers=h).json()["status"] == "cancelled"
    assert client.post(f"{base}/{b}/reschedule", headers=h, json={"performed_on": future.isoformat()}).status_code == 409
    assert client.post(f"{base}/{a}/reschedule", headers=h, json={"performed_on": "2000-01-02"}).status_code == 422
    assert client.post(f"{base}/{a}/reschedule", headers=h, json={}).status_code == 422
    assert client.post(f"{base}/{a}/reschedule", json={"performed_on": future.isoformat()}).status_code == 401

"""T029 - G6: F4 has no object storage: any storage key or URL from a client is `invalid_object_ref` (REST and sync); no signed URL is issued."""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import SYSTEM_BODY, call, sync_event, sync_op, sync_post, world4  # noqa: F401

BAD = [{"file_key": "farms/x/y"}, {"object_key": "k"}, {"url": "https://evil.test/x"}, {"photo_key": "farms/x/zone-photos/y"}]


def _p(w):
    return f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}"


@pytest.mark.parametrize("extra", BAD, ids=lambda e: next(iter(e)))
def test_given_a_storage_key_or_url_in_a_rest_body_then_422_invalid_object_ref_and_nothing_is_written(client, token_for, world4, extra):
    w = world4
    tok = token_for(w["owner"])
    ok = call(client, tok, "POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30})
    assert ok.status_code == 201, ok.text
    before = sql("SELECT count(*) FROM irrigation_events")[0][0]
    for method, path, body in [("POST", f"{_p(w)}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30, **extra}),
                               ("PUT", f"{_p(w)}/irrigation-system", {**SYSTEM_BODY, **extra}),
                               ("POST", f"{_p(w)}/water-analyses", {"id": str(uuid.uuid4()), "ec_ds_m": 2.0, "analysed_on": "2026-06-01", **extra})]:
        r = call(client, tok, method, path, body)
        assert r.status_code == 422 and "invalid_object_ref" in r.text, (path, r.status_code, r.text)
    assert sql("SELECT count(*) FROM irrigation_events")[0][0] == before


@pytest.mark.parametrize("extra", BAD, ids=lambda e: next(iter(e)))
def test_given_a_storage_key_or_url_in_a_sync_op_then_invalid_object_ref_and_nothing_is_written(client, token_for, world4, extra):
    w, rid = world4, uuid.uuid4()
    assert sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 200
    r = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"], rid, **extra)])
    assert "invalid_object_ref" in r.text and r.status_code in (200, 422), r.text
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", rid)[0][0] == 0
    op = sync_op("irrigation_systems", w["farm_a"], uuid.uuid4(), {"parcel_id": str(w["p"][9]), "kind": "drip", "sectors_count": 1, "pump_flow_m3h": 5, **extra})
    assert "invalid_object_ref" in sync_post(client, token_for(w["owner"]), [op]).text


def test_given_any_f4_response_then_no_signed_url_or_storage_key_is_ever_emitted(client, token_for, world4):
    from tests.integration._f4 import keys_of

    w = world4
    tok, f = token_for(w["owner"]), f"/v1/farms/{w['farm_a']}"
    for path in ("irrigation/advice", "irrigation/consumption", f"parcels/{w['a1']}/irrigation/advice", f"parcels/{w['a1']}/irrigation/events",
                 f"parcels/{w['a1']}/irrigation-system", f"parcels/{w['a1']}/water-analyses", f"parcels/{w['a1']}/irrigation/balance"):
        r = call(client, tok, "GET", f"{f}/{path}")
        assert r.status_code == 200, path
        assert "X-Amz-" not in r.text and "http://" not in r.text and "https://" not in r.text, path
        assert not [k for k in keys_of(r.json()) if k.endswith(("_key", "_url")) or k in ("url", "key_path")], path


def test_given_client_chosen_ids_then_they_are_attached_to_the_farm_server_side_and_never_to_another_farm(client, token_for, world4):
    w = world4
    mine = uuid.uuid4()
    r = call(client, token_for(w["owner"]), "POST", f"{_p(w)}/irrigation/events", {"id": str(mine), "performed_on": "2026-06-03", "duration_min": 30})
    assert r.status_code == 201
    assert sql("SELECT farm_id FROM irrigation_events WHERE id=$1", mine)[0][0] == w["farm_a"]
    again = call(client, token_for(w["owner_b"]), "POST", f"/v1/farms/{w['farm_b']}/parcels/{w['b1']}/irrigation/events", {"id": str(mine), "performed_on": "2026-06-03", "duration_min": 30})
    assert again.status_code in (404, 409, 422) and sql("SELECT farm_id FROM irrigation_events WHERE id=$1", mine)[0][0] == w["farm_a"]

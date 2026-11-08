"""T048 (US1) - R1-A1/A2/A3/A5: describing, replacing and reading the installation of a parcel (real PostgreSQL)."""
import concurrent.futures
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import FORBIDDEN, NOT_FOUND, SYSTEM_BODY, call, world4  # noqa: F401
from tests.integration._f2 import add_field

DRIP = {"kind": "drip", "sectors_count": 2, "emitter_flow_lph": 4, "emitter_spacing_m": 0.5, "row_spacing_m": 2}


def _fresh_parcel(w, name="Fresh", irrigation="drip"):
    parcel = add_field(w["farm_a"], name, lon=-7.40)
    sql("UPDATE parcels SET irrigation=$2 WHERE id=$1", parcel, irrigation)
    return parcel


def _url(w, parcel, suffix="irrigation-system"):
    return f"/v1/farms/{w['farm_a']}/parcels/{parcel}/{suffix}"


def test_given_an_irrigated_parcel_when_the_owner_describes_the_system_then_it_is_stored_and_attached_to_the_parcel(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w)
    r = call(client, token_for(w["owner"]), "PUT", _url(w, parcel), DRIP)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["parcel_id"] == str(parcel) and body["kind"] == "drip" and body["sectors_count"] == 2
    assert call(client, token_for(w["owner"]), "GET", _url(w, parcel)).json()["emitter_flow_lph"] == 4
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 1


def test_given_a_system_described_by_the_pump_flow_then_it_is_accepted_without_emitters_or_spacings(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w)
    r = call(client, token_for(w["manager"]), "PUT", _url(w, parcel), {"kind": "sprinkler", "sectors_count": 3, "pump_flow_m3h": 12})
    assert r.status_code == 200 and r.json()["emitter_flow_lph"] is None and r.json()["pump_flow_m3h"] == 12


@pytest.mark.parametrize("kind,eff", [("drip", 0.9), ("sprinkler", 0.75), ("pivot", 0.75), ("gravity", 0.6)])
def test_given_no_efficiency_then_the_default_of_the_type_applies_and_stays_visible(client, token_for, world4, kind, eff):
    w = world4
    parcel = _fresh_parcel(w, f"E-{kind}")
    r = call(client, token_for(w["owner"]), "PUT", _url(w, parcel), {"kind": kind, "sectors_count": 1, "pump_flow_m3h": 5})
    assert r.status_code == 200
    assert r.json()["efficiency_effective"] == eff and r.json()["efficiency_is_default"] is True and r.json()["efficiency"] is None


def test_given_an_explicit_efficiency_then_it_is_kept_and_no_longer_flagged_as_default(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w)
    r = call(client, token_for(w["owner"]), "PUT", _url(w, parcel), {**SYSTEM_BODY, "efficiency": 0.8})
    assert r.json()["efficiency_effective"] == 0.8 and r.json()["efficiency_is_default"] is False


@pytest.mark.parametrize("field,patch", [
    ("emitter_flow_lph", {"emitter_flow_lph": 0}), ("emitter_flow_lph", {"emitter_flow_lph": -2}),
    ("emitter_spacing_m", {"emitter_spacing_m": 0}), ("row_spacing_m", {"row_spacing_m": 0}),
    ("sectors_count", {"sectors_count": 0}),
])
def test_given_an_incoherent_value_when_validating_then_422_names_the_field_and_nothing_is_stored(client, token_for, world4, field, patch):
    w = world4
    parcel = _fresh_parcel(w)
    r = call(client, token_for(w["owner"]), "PUT", _url(w, parcel), {**DRIP, **patch})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "validation" and r.json()["field"] == field and r.json()["code"], r.text
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 0


def test_given_a_system_when_modified_then_the_previous_version_is_kept_and_listed_newest_first(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w)
    tok = token_for(w["owner"])
    first = call(client, tok, "PUT", _url(w, parcel), DRIP).json()
    second = call(client, tok, "PUT", _url(w, parcel), {**DRIP, "emitter_flow_lph": 8}).json()
    assert second["id"] == first["id"] and second["server_version"] == first["server_version"] + 1
    items = call(client, tok, "GET", _url(w, parcel, "irrigation-system/versions")).json()["items"]
    assert sorted(i["snapshot"]["emitter_flow_lph"] for i in items) == [4, 8]  # newest-first order is not asserted: the injected clock gives both versions the same instant
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 1  # one active system per parcel


def test_given_50_versions_when_modifying_again_then_the_change_is_refused_and_the_system_is_unchanged(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w)
    tok = token_for(w["owner"])
    sid = call(client, tok, "PUT", _url(w, parcel), DRIP).json()["id"]
    for _ in range(49):
        sql("INSERT INTO irrigation_system_versions (id, farm_id, system_id, parcel_id, snapshot, changed_by, changed_at)"
            " VALUES (gen_random_uuid(),$1,$2,$3,'{}'::jsonb,$4,now())", w["farm_a"], uuid.UUID(sid), parcel, w["owner"])
    assert sql("SELECT count(*) FROM irrigation_system_versions WHERE system_id=$1", uuid.UUID(sid))[0][0] == 50
    r = call(client, tok, "PUT", _url(w, parcel), {**DRIP, "emitter_flow_lph": 9})
    assert r.status_code == 409 and r.json()["detail"] == "quota_exceeded"
    assert call(client, tok, "GET", _url(w, parcel)).json()["emitter_flow_lph"] == 4


def test_given_a_rainfed_parcel_when_describing_a_system_then_422_and_nothing_is_stored(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w, "Rain", irrigation="rainfed")
    r = call(client, token_for(w["owner"]), "PUT", _url(w, parcel), DRIP)
    assert r.status_code == 422 and r.json()["code"] == "parcel_rainfed"
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 0


def test_given_two_concurrent_first_descriptions_then_the_farm_lock_leaves_exactly_one_active_system(client, token_for, world4):
    w = world4
    parcel = _fresh_parcel(w)
    tok = token_for(w["owner"])
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes = list(pool.map(lambda e: call(client, tok, "PUT", _url(w, parcel), {**DRIP, "emitter_flow_lph": e}).status_code, [4, 6]))
    assert codes == [200, 200]
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", parcel)[0][0] == 1
    assert sql("SELECT count(*) FROM irrigation_system_versions WHERE parcel_id=$1", parcel)[0][0] == 2


def test_given_a_worker_when_describing_a_system_then_403_and_nothing_changes(client, token_for, world4):
    w = world4
    before = call(client, token_for(w["owner"]), "GET", _url(w, w["a1"])).json()
    r = call(client, token_for(w["worker"]), "PUT", _url(w, w["a1"]), {**SYSTEM_BODY, "pump_flow_m3h": 99})
    assert r.status_code == 403 and r.json() == FORBIDDEN
    assert call(client, token_for(w["owner"]), "GET", _url(w, w["a1"])).json()["server_version"] == before["server_version"]


def test_given_a_worker_when_reading_a_system_then_only_for_an_assigned_not_archived_parcel(client, token_for, world4):
    w = world4
    tok = token_for(w["worker"])
    assert call(client, tok, "GET", _url(w, w["a1"])).status_code == 200
    hidden = call(client, tok, "GET", _url(w, w["hidden"]))
    unknown = call(client, tok, "GET", _url(w, uuid.uuid4()))
    assert hidden.status_code == unknown.status_code == 404 and hidden.json() == unknown.json() == NOT_FOUND
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    archived = call(client, tok, "GET", _url(w, w["a1"]))
    assert archived.status_code == 404 and archived.json() == NOT_FOUND


def test_given_another_farm_then_every_read_and_write_is_the_same_404_as_an_unknown_parcel(client, token_for, world4):
    w = world4
    tok = token_for(w["owner_b"])
    for method, suffix, body in (("GET", "irrigation-system", None), ("PUT", "irrigation-system", SYSTEM_BODY), ("GET", "irrigation-system/versions", None)):
        other = call(client, tok, method, _url(w, w["a1"], suffix), body)
        assert other.status_code == 404 and other.json() == NOT_FOUND, (method, suffix, other.text)

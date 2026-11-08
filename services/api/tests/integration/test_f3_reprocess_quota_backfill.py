"""Defect 2 - the farm cap of 5 active imagery jobs counts reprocessing jobs only: initial-history (`backfill`) jobs created with the parcels
must not use it up. Per parcel the daily cap stays 3."""
import uuid

from tests.helpers import auth, sql
from tests.integration._f2 import square
from tests.integration._f3 import new_user  # noqa: F401


def _farm_with_parcels(client, token_for, make_farm, n=5):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    tok = token_for(owner)
    parcels = []
    for i in range(n):
        r = client.post(f"/v1/farms/{farm}/fields", headers=auth(tok), json={"name": f"Q{i}", "geometry": square(-7.30 + i * 0.01)})
        assert r.status_code == 201, r.text
        parcels.append(r.json()["id"])
    return farm, tok, parcels


def _reprocess(client, tok, farm, parcel):
    return client.post(f"/v1/farms/{farm}/parcels/{parcel}/vigor/reprocess", headers=auth(tok))


def test_given_a_farm_with_5_parcels_just_created_when_asking_a_reprocessing_then_it_is_accepted(client, token_for, make_farm):
    farm, tok, parcels = _farm_with_parcels(client, token_for, make_farm)
    assert sql("SELECT count(*) FROM monitoring_jobs WHERE farm_id = $1 AND kind = 'backfill' AND state = 'queued'", farm)[0][0] == 5
    r = _reprocess(client, tok, farm, parcels[0])
    assert r.status_code == 202, r.text


def test_given_5_initial_history_jobs_when_asking_reprocessings_then_5_are_accepted_and_the_6th_gets_429_with_its_quota_code(client, token_for, make_farm):
    farm, tok, parcels = _farm_with_parcels(client, token_for, make_farm)
    targets = [parcels[0]] * 3 + [parcels[1]] * 2  # at most 3 per parcel and per day
    assert [_reprocess(client, tok, farm, p).status_code for p in targets] == [202] * 5
    sixth = _reprocess(client, tok, farm, parcels[1])
    assert sixth.status_code == 429 and sixth.json()["detail"]["code"] == "quota_exceeded" and "retry-after" in sixth.headers
    assert sql("SELECT count(*) FROM monitoring_jobs WHERE farm_id = $1 AND kind = 'reprocess'", farm)[0][0] == 5


def test_given_a_parcel_with_3_reprocessings_today_when_asking_a_4th_then_429_even_with_free_farm_slots(client, token_for, make_farm):
    farm, tok, parcels = _farm_with_parcels(client, token_for, make_farm, n=1)
    assert [_reprocess(client, tok, farm, parcels[0]).status_code for _ in range(3)] == [202] * 3
    r = _reprocess(client, tok, farm, parcels[0])
    assert r.status_code == 429 and r.json()["detail"]["code"] == "quota_exceeded"


def test_given_finished_reprocessings_when_asking_again_then_they_no_longer_count_against_the_farm_cap(client, token_for, make_farm):
    farm, tok, parcels = _farm_with_parcels(client, token_for, make_farm)
    for p in [parcels[0]] * 3 + [parcels[1]] * 2:
        assert _reprocess(client, tok, farm, p).status_code == 202
    sql("UPDATE monitoring_jobs SET state = 'done', finished_at = now() WHERE farm_id = $1 AND kind = 'reprocess'", farm)
    assert _reprocess(client, tok, farm, parcels[2]).status_code == 202
    assert uuid.UUID(str(farm))

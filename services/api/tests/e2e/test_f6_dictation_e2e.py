"""T067 - R5-A4 on the running stack: a dictation analysis records nothing; only the confirmed form creates an operation.

The stack ships with AYLAL_NLU_URL empty (nothing external by default): the analysis answers 503 and the form-by-icons path
still records the operation.
"""
import httpx

from tests.e2e._f6 import BASE, body, field_with_crop, owner_with_farm, unique_phone
from tests.helpers import sql

PHONE = unique_phone()


def test_given_a_dictation_when_it_is_not_confirmed_then_no_operation_is_recorded_and_the_icon_form_still_works() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        parcel, _ = field_with_crop(c, h, farm, "A", -7.60)
        parse = c.post(f"/farms/{farm}/operations/parse", headers=h, json={"text": "j'ai arrosé les oliviers"})
        assert parse.status_code in (200, 503), parse.text
        if parse.status_code == 200:
            assert parse.json()["requires_confirmation"] is True
        else:
            assert parse.json() == {"code": "parse_unavailable"}
        assert c.get(f"/farms/{farm}/operations", headers=h).json()["items"] == []
        assert sql("SELECT count(*) FROM operations WHERE farm_id=$1::uuid", farm)[0][0] == 0
        too_long = c.post(f"/farms/{farm}/operations/parse", headers=h, json={"text": "a" * 501})
        assert too_long.status_code == 422
        assert c.post(f"/farms/{farm}/operations", headers=h, json=body([parcel])).status_code == 201

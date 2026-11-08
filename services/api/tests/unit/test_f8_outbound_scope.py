"""T011 - G5: outbound requests carry exact allow-listed keys (image only for OCR; crops and date window for prices; no farm, user or parcel id);
sending is refused unless the receipt belongs to the caller's farm, is `uploaded`, the membership is active, the daily cap is not hit and the host is listed."""
import datetime as dt
import uuid

import pytest

FORBIDDEN = ("farm_id", "user_id", "parcel_id", "author_id", "phone", "phone_e164", "name", "geometry", "expense_id", "receipt_id", "object_key", "season_id")
FARM = uuid.uuid4()
RECEIPT = {"id": uuid.uuid4(), "farm_id": FARM, "status": "uploaded", "content_type": "image/jpeg", "size_bytes": 1000}
URL, HOSTS = "https://ocr.example.ma/read", ("ocr.example.ma",)


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return {"confidence": 0.5}


def _sent_keys(call):
    _, _, kw = call
    keys = set()
    for part in ("params", "json", "data", "files"):
        keys |= set(kw.get(part) or {})
    return keys


def test_given_the_allow_list_then_ocr_and_prices_have_the_exact_keys():
    from app.economics.gateways import OUTBOUND_ALLOWLIST

    assert OUTBOUND_ALLOWLIST["ocr"] == frozenset({"image", "lang"})
    assert OUTBOUND_ALLOWLIST["market_prices"] == frozenset({"crops", "from", "to"})


def test_given_an_ocr_read_then_the_request_carries_the_image_and_the_language_only():
    from app.domain.clock import FixedClock
    from app.economics.gateways import OcrGateway

    spy = Spy()
    OcrGateway(url=URL, allowed_hosts=HOSTS, http=spy, clock=FixedClock(dt.datetime(2026, 6, 4, tzinfo=dt.UTC))).read(
        image=b"\xff\xd8\xff\xe0" + b"0" * 16, content_type="image/jpeg", lang="fr")
    assert len(spy.calls) == 1 and _sent_keys(spy.calls[0]) == {"image", "lang"}


def test_given_a_prices_request_then_the_keys_are_exact_and_the_crops_are_referential_slugs():
    from app.economics.gateways import build_market_prices_request

    req = build_market_prices_request(crops=["tomato", "olive"], date_from="2026-03-05", date_to="2026-06-04")
    assert set(req) == {"crops", "from", "to"} and req["crops"] == ["tomato", "olive"]


def test_given_a_prices_window_over_92_days_then_the_request_is_refused():
    from app.economics.gateways import build_market_prices_request

    with pytest.raises(ValueError):
        build_market_prices_request(crops=["tomato"], date_from="2025-01-01", date_to="2026-06-04")


@pytest.mark.parametrize("kind", ["ocr", "market_prices"])
@pytest.mark.parametrize("extra", FORBIDDEN)
def test_given_any_farm_user_or_parcel_field_then_the_outbound_guard_refuses_it(kind, extra):
    from app.economics.gateways import OUTBOUND_ALLOWLIST, assert_outbound

    ok = {k: "x" for k in OUTBOUND_ALLOWLIST[kind]}
    assert_outbound(kind, ok)
    with pytest.raises(ValueError):
        assert_outbound(kind, {**ok, extra: "x"})


def test_given_a_missing_key_then_the_guard_refuses_so_keys_are_exact():
    from app.economics.gateways import assert_outbound

    with pytest.raises(ValueError):
        assert_outbound("ocr", {"image": b"x"})


def _prepare(**over):
    from app.economics.gateways import prepare_ocr_send

    args = dict(receipt=RECEIPT, caller_farm=FARM, membership_active=True, reads_today=0, url=URL, allowed_hosts=HOSTS)
    args.update(over)
    return prepare_ocr_send(**args)


def test_given_a_valid_scope_then_the_send_is_authorised():
    _prepare()


@pytest.mark.parametrize("over,reason", [
    ({"caller_farm": uuid.uuid4()}, "farm_mismatch"),
    ({"receipt": {**RECEIPT, "status": "reading"}}, "not_uploaded"),
    ({"receipt": {**RECEIPT, "status": "ready"}}, "not_uploaded"),
    ({"membership_active": False}, "membership_inactive"),
    ({"reads_today": 100}, "daily_cap"),
    ({"url": "https://evil.example.com/x"}, "host_not_listed"),
    ({"url": ""}, "host_not_listed"),
], ids=["other-farm", "reading", "ready", "removed-member", "daily-cap", "foreign-host", "empty-url"])
def test_given_a_scope_violation_then_the_send_is_refused_with_its_reason_before_any_call(over, reason):
    from app.economics.gateways import OutboundRefused

    with pytest.raises(OutboundRefused) as exc:
        _prepare(**over)
    assert exc.value.reason == reason


def test_given_99_reads_today_then_the_100th_is_still_allowed():
    _prepare(reads_today=99)

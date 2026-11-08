"""T010 - G5: AYLAL_OCR_URL / AYLAL_MARKET_PRICES_URL empty by default; empty URL, unlisted host, mute, malformed or out-of-bounds answer ->
`availability: unavailable` + reason, never an invented, interpolated or default value (R1-A2, R5-A2, FR-013)."""
import datetime as dt

import pytest

NOW = dt.datetime(2026, 6, 4, 12, 0, tzinfo=dt.UTC)
VALUE_FIELDS = {"proposal", "amount_cents", "date", "category", "rows", "prices", "price_cents"}
OCR_OK = {"amount_cents": 12500, "date": "2026-06-01", "category": "fuel", "confidence": 0.8}
PRICE_ROW = {"crop_slug": "tomato", "market": "Casablanca", "unit": "kg", "price_cents": 450, "observed_on": "2026-06-02", "source": "mercuriale"}


class Spy:
    def __init__(self, response=None, error=None):
        self.calls, self.response, self.error = [], response, error

    def __call__(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if self.error:
            raise self.error
        return self.response


def _clock():
    from app.domain.clock import FixedClock

    return FixedClock(NOW)


def _ocr(url, hosts, spy):
    from app.economics.gateways import OcrGateway

    return OcrGateway(url=url, allowed_hosts=hosts, http=spy, clock=_clock())


def _prices(url, hosts, spy):
    from app.economics.gateways import MarketPricesGateway

    return MarketPricesGateway(url=url, allowed_hosts=hosts, http=spy, clock=_clock())


def _read(g):
    return g.read(image=b"\xff\xd8\xff\xe0" + b"0" * 32, content_type="image/jpeg", lang="fr")


def _fetch(g):
    return g.fetch(crops=["tomato"], date_from="2026-03-05", date_to="2026-06-04")


def _unavailable(res, reason):
    assert res["availability"] == "unavailable" and res["reason"] == reason
    assert not (set(res) & VALUE_FIELDS), f"invented value fields: {set(res) & VALUE_FIELDS}"


def test_given_the_default_settings_then_both_gateway_urls_are_empty(monkeypatch):
    monkeypatch.delenv("AYLAL_OCR_URL", raising=False)
    monkeypatch.delenv("AYLAL_MARKET_PRICES_URL", raising=False)
    from app.config import get_settings

    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    s = get_settings()
    assert s.ocr_url == "" and s.market_prices_url == ""


@pytest.mark.parametrize("make,call", [(_ocr, _read), (_prices, _fetch)], ids=["ocr", "prices"])
def test_given_an_empty_url_then_unavailable_not_configured_and_zero_calls(make, call):
    spy = Spy()
    _unavailable(call(make("", (), spy)), "gateway_not_configured")
    assert spy.calls == []


@pytest.mark.parametrize("make,call", [(_ocr, _read), (_prices, _fetch)], ids=["ocr", "prices"])
def test_given_a_host_outside_the_allow_list_then_unavailable_and_zero_calls(make, call):
    spy = Spy()
    _unavailable(call(make("https://evil.example.com/x", ("ocr.example.ma",), spy)), "gateway_not_configured")
    assert spy.calls == []


@pytest.mark.parametrize("make,call", [(_ocr, _read), (_prices, _fetch)], ids=["ocr", "prices"])
def test_given_an_unreachable_gateway_then_unavailable_without_a_default_value(make, call):
    _unavailable(call(make("https://gw.example.ma/x", ("gw.example.ma",), Spy(error=OSError("down")))), "gateway_unreachable")


@pytest.mark.parametrize("make,call,bad", [
    (_ocr, _read, {"amount_cents": "12,5", "confidence": 0.8}),
    (_ocr, _read, "not json at all"),
    (_prices, _fetch, {"rows": "oops"}),
    (_prices, _fetch, None),
], ids=["ocr-type", "ocr-garbage", "prices-type", "prices-none"])
def test_given_a_malformed_answer_then_unavailable_malformed_and_nothing_is_kept(make, call, bad):
    _unavailable(call(make("https://gw.example.ma/x", ("gw.example.ma",), Spy(response=bad))), "malformed_response")


@pytest.mark.parametrize("make,call,bad", [
    (_ocr, _read, {**OCR_OK, "amount_cents": -5}),
    (_ocr, _read, {**OCR_OK, "date": "2026-06-30"}),
    (_ocr, _read, {**OCR_OK, "category": "crypto"}),
    (_prices, _fetch, {"rows": [{**PRICE_ROW, "price_cents": -1}]}),
    (_prices, _fetch, {"rows": [{**PRICE_ROW, "observed_on": "2026-06-30"}]}),
    (_prices, _fetch, {"rows": [{**PRICE_ROW, "crop_slug": "not-asked"}]}),
    (_prices, _fetch, {"rows": [{k: v for k, v in PRICE_ROW.items() if k != "source"}]}),
], ids=["ocr-negative", "ocr-future", "ocr-category", "price-negative", "price-future", "price-crop", "price-no-source"])
def test_given_an_out_of_bounds_answer_then_unavailable_out_of_bounds_and_the_whole_answer_is_rejected(make, call, bad):
    _unavailable(call(make("https://gw.example.ma/x", ("gw.example.ma",), Spy(response=bad))), "out_of_bounds")


def test_given_a_valid_ocr_answer_then_it_is_a_proposal_with_exactly_what_the_gateway_said():
    spy = Spy(response=OCR_OK)
    res = _read(_ocr("https://gw.example.ma/x", ("gw.example.ma",), spy))
    assert res["availability"] == "ok" and res["proposal"] == OCR_OK and len(spy.calls) == 1


def test_given_a_partial_ocr_answer_then_missing_fields_stay_missing():
    res = _read(_ocr("https://gw.example.ma/x", ("gw.example.ma",), Spy(response={"confidence": 0.1})))
    assert res["availability"] == "ok" and res["proposal"] == {"confidence": 0.1}


def test_given_valid_price_rows_then_every_row_keeps_its_source_and_date():
    res = _fetch(_prices("https://gw.example.ma/x", ("gw.example.ma",), Spy(response={"rows": [PRICE_ROW]})))
    assert res["availability"] == "ok" and res["rows"] == [PRICE_ROW]
    assert all(r["source"] and r["observed_on"] for r in res["rows"])

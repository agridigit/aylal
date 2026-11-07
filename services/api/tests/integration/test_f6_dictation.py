"""T066 - R5: the VoiceParser port. Text only (<= 500 chars), audio never sent, unavailable -> fallback, 60/h per user,
the analysis proposes a draft and never records anything. Nothing external is called by default (AYLAL_NLU_URL empty -> 503)."""
import socket

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import world  # noqa: F401

NLU = "http://nlu.invalid"


class FakeParser:
    """Stands for the VoiceParser port: `async parse(text, *, parcels) -> {"draft": {...}, "ambiguous": [...]}`."""

    def __init__(self, result=None, fail=False):
        self.result = result if result is not None else {"draft": {"type": "irrigation"}, "ambiguous": []}
        self.fail, self.calls = fail, []

    async def parse(self, text, *, parcels):
        self.calls.append((text, parcels))
        if self.fail:
            raise TimeoutError("nlu down")
        return self.result


@pytest.fixture
def parser(client, monkeypatch):
    monkeypatch.setenv("AYLAL_NLU_URL", NLU)

    def install(fake):
        from app.main import app
        from app.operations import parse

        app.dependency_overrides[parse.get_voice_parser] = lambda: fake
        return fake

    yield install
    from app.main import app
    from app.operations import parse

    app.dependency_overrides.pop(parse.get_voice_parser, None)


def post(client, token_for, who, farm, body):
    return client.post(f"/v1/farms/{farm}/operations/parse", headers=auth(token_for(who)), json=body)


def counts():
    return [sql(f"SELECT count(*) FROM {t}")[0][0] for t in ("operations", "operation_parcels", "registry_entries", "label_uploads", "applied_ops")]


def test_given_no_nlu_url_when_parsing_then_503_and_no_network_call_is_made(client, token_for, world, monkeypatch):
    from app.operations import parse  # noqa: F401  (the port module exists)

    monkeypatch.setenv("AYLAL_NLU_URL", "")

    def forbidden(*a, **k):
        raise AssertionError("an external connection was attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    r = post(client, token_for, world["owner"], world["farm_a"], {"text": "j'ai arrosé"})
    assert r.status_code == 503 and r.json()["code"] == "parse_unavailable"


def test_given_a_parser_when_parsing_then_the_draft_and_the_ambiguous_fields_are_returned_for_confirmation(client, token_for, world, parser):
    w = world
    fake = parser(FakeParser({"draft": {"type": "phyto", "product_query": "cuivre"},
                              "ambiguous": [{"field": "parcel_ids", "candidates": [str(w["a1"]), str(w["a2"])]}]}))
    r = post(client, token_for, w["owner"], w["farm_a"], {"text": "j'ai traité les oliviers avec du cuivre"})
    assert r.status_code == 200, r.text
    assert r.json() == {"understood": True, "requires_confirmation": True, "draft": {"type": "phyto", "product_query": "cuivre"},
                        "ambiguous": [{"field": "parcel_ids", "candidates": [str(w["a1"]), str(w["a2"])]}]}
    assert len(fake.calls) == 1


def test_given_a_parser_that_understands_nothing_when_parsing_then_an_empty_draft_is_returned_so_the_form_opens_empty(client, token_for, world, parser):
    parser(FakeParser({"draft": {}, "ambiguous": []}))
    r = post(client, token_for, world["owner"], world["farm_a"], {"text": "bla bla xyz"})
    assert r.status_code == 200
    assert r.json() == {"understood": False, "requires_confirmation": True, "draft": {}, "ambiguous": []}


def test_given_an_unavailable_parser_when_parsing_then_503_parse_unavailable_and_nothing_is_recorded(client, token_for, world, parser):
    parser(FakeParser(fail=True))
    before = counts()
    r = post(client, token_for, world["owner"], world["farm_a"], {"text": "j'ai arrosé"})
    assert r.status_code == 503 and r.json()["code"] == "parse_unavailable"
    assert counts() == before


def test_given_a_parsed_dictation_when_nothing_is_confirmed_then_no_operation_or_registry_row_exists(client, token_for, world, parser):
    w = world
    parser(FakeParser({"draft": {"type": "phyto", "parcel_ids": [str(w["a1"])]}, "ambiguous": []}))
    before = counts()
    for who in ("owner", "manager", "worker"):
        assert post(client, token_for, w[who], w["farm_a"], {"text": "j'ai traité"}).status_code == 200
    assert counts() == before


def test_given_a_text_over_500_characters_when_parsing_then_422_before_any_analysis(client, token_for, world, parser):
    fake = parser(FakeParser())
    assert post(client, token_for, world["owner"], world["farm_a"], {"text": "a" * 501}).status_code == 422
    assert fake.calls == []
    assert post(client, token_for, world["owner"], world["farm_a"], {"text": "a" * 500}).status_code == 200


@pytest.mark.parametrize("extra", [{"audio": "AAAA"}, {"audio_url": "https://x"}, {"url": "https://x"}, {"file_keys": ["k"]}])
def test_given_audio_or_a_url_in_the_body_when_parsing_then_422_and_the_parser_is_not_called(client, token_for, world, parser, extra):
    fake = parser(FakeParser())
    assert post(client, token_for, world["owner"], world["farm_a"], {"text": "irrigation", **extra}).status_code == 422
    assert fake.calls == []


def test_given_a_parser_when_parsing_then_it_receives_only_the_text_and_the_parcels_visible_to_the_user(client, token_for, world, parser):
    w = world
    fake = parser(FakeParser())
    assert post(client, token_for, w["worker"], w["farm_a"], {"text": "j'ai arrosé"}).status_code == 200
    text, parcels = fake.calls[0]
    assert isinstance(text, str) and text == "j'ai arrosé"
    assert [p["id"] for p in parcels] == [str(w["a1"])]  # the worker is assigned a1 only; no other farm
    assert set(parcels[0]) <= {"id", "name"}
    fake.calls.clear()
    post(client, token_for, w["owner"], w["farm_a"], {"text": "j'ai arrosé"})
    assert sorted(p["id"] for p in fake.calls[0][1]) == sorted([str(w["a1"]), str(w["a2"])])


def test_given_a_parser_that_names_parcels_the_user_cannot_see_when_parsing_then_they_are_dropped(client, token_for, world, parser):
    w = world
    parser(FakeParser({"draft": {"type": "irrigation", "parcel_ids": [str(w["a1"]), str(w["b1"]), str(w["a2"])]},
                       "ambiguous": [{"field": "parcel_ids", "candidates": [str(w["b1"]), str(w["a2"])]}]}))
    r = post(client, token_for, w["worker"], w["farm_a"], {"text": "irrigation"})
    assert r.status_code == 200, r.text
    assert r.json()["draft"]["parcel_ids"] == [str(w["a1"])]
    assert r.json()["ambiguous"][0]["candidates"] == []


def test_given_another_farm_or_a_non_member_when_parsing_then_404_and_the_parser_is_not_called(client, token_for, world, parser):
    w = world
    fake = parser(FakeParser())
    unknown = post(client, token_for, w["owner_b"], "00000000-0000-4000-8000-000000000000", {"text": "x"})
    for who in ("owner_b", "outsider"):
        r = post(client, token_for, w[who], w["farm_a"], {"text": "x"})
        assert r.status_code == 404 and r.json() == unknown.json()
    assert fake.calls == []
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/parse", json={"text": "x"}).status_code == 401


def test_given_the_hourly_limit_of_one_user_when_exceeded_then_429_before_the_parser_and_other_users_are_unaffected(client, token_for, world, parser):
    w = world
    fake = parser(FakeParser())
    h = auth(token_for(w["owner"]))
    url = f"/v1/farms/{w['farm_a']}/operations/parse"
    codes = [client.post(url, headers=h, json={"text": "x"}).status_code for _ in range(61)]
    assert codes[:60] == [200] * 60 and codes[60] == 429
    assert len(fake.calls) == 60
    assert client.post(url, headers=h, json={"text": "x"}).headers["Retry-After"]
    assert post(client, token_for, w["manager"], w["farm_a"], {"text": "x"}).status_code == 200

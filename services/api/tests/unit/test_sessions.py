"""T020 - refresh token rotation and reuse detection (R1-A4)."""
import datetime as dt
import uuid

from app.auth import sessions

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def _record(family, token="t", **kw):
    return sessions.TokenRecord(
        id=uuid.uuid4(), family_id=family, token_hash=sessions.hash_token(token),
        rotated_at=kw.get("rotated_at"), revoked_at=kw.get("revoked_at"),
    )


def test_given_a_token_when_hashed_then_the_hash_is_stable_and_not_the_token():
    assert sessions.hash_token("abc") == sessions.hash_token("abc")
    assert sessions.hash_token("abc") != "abc"


def test_given_two_new_tokens_then_they_are_long_and_different():
    a, b = sessions.new_token(), sessions.new_token()
    assert a != b and len(a) >= 40


def test_given_a_live_token_when_refreshing_then_the_decision_is_rotate():
    assert sessions.evaluate(_record(uuid.uuid4()), NOW) == "rotate"


def test_given_an_already_rotated_token_when_presented_then_reuse_is_detected():
    rec = _record(uuid.uuid4(), rotated_at=NOW)
    assert sessions.evaluate(rec, NOW) == "reuse"


def test_given_a_revoked_token_when_presented_then_it_is_refused():
    assert sessions.evaluate(_record(uuid.uuid4(), revoked_at=NOW), NOW) == "revoked"


def test_given_a_reuse_when_revoking_the_family_then_only_that_family_is_revoked():
    fam, other = uuid.uuid4(), uuid.uuid4()
    recs = [_record(fam, "a"), _record(fam, "b"), _record(other, "c")]
    out = sessions.revoke_family(recs, fam, NOW)
    assert [r.revoked_at for r in out] == [NOW, NOW, None]


def test_given_a_rotation_then_the_new_token_keeps_the_family_and_the_old_one_is_marked_rotated():
    fam = uuid.uuid4()
    old = _record(fam)
    old2, new, raw = sessions.rotate(old, NOW)
    assert old2.rotated_at == NOW
    assert new.family_id == fam and new.token_hash == sessions.hash_token(raw)
    assert new.token_hash != old.token_hash

"""T019 - OTP generation, argon2 + pepper hashing, expiry, constant-time compare, failure counter (R1-A1, R1-A2)."""
import re

from app.auth import otp
from app.domain import otp_policy

PEPPER = "p" * 40


def test_given_a_new_code_when_generated_then_it_is_six_digits_and_varies():
    codes = {otp.new_code() for _ in range(50)}
    assert all(re.fullmatch(r"\d{6}", c) for c in codes)
    assert len(codes) > 1


def test_given_a_code_when_hashed_then_the_hash_is_argon2id_and_does_not_contain_the_code():
    h = otp.hash_code("123456", PEPPER)
    assert h.startswith("$argon2id$")
    assert "123456" not in h and PEPPER not in h


def test_given_two_hashes_of_the_same_code_when_compared_then_salts_differ():
    assert otp.hash_code("123456", PEPPER) != otp.hash_code("123456", PEPPER)


def test_given_another_pepper_when_checking_the_right_code_then_it_is_refused():
    h = otp.hash_code("123456", PEPPER)
    assert otp.check_code("123456", h, PEPPER) is True
    assert otp.check_code("123456", h, "q" * 40) is False


def test_given_a_code_older_than_its_expiry_when_checked_then_it_is_expired():
    assert otp_policy.is_expired(expires_at_ms=1_000, now_ms=1_000) is True
    assert otp_policy.is_expired(expires_at_ms=1_000, now_ms=999) is False


def test_given_two_failures_when_asking_attempts_left_then_one_remains():
    state = {"failed_attempts": 2, "locked_until_ms": None}
    assert otp_policy.attempts_left(state) == 1
    assert otp_policy.attempts_left({"failed_attempts": 3, "locked_until_ms": 5}) == 0


def test_given_three_failures_when_registered_then_the_lock_lasts_five_minutes():
    state = {"failed_attempts": 0, "locked_until_ms": None}
    for _ in range(3):
        state = otp_policy.register_failure(state, 10_000)
    assert state["locked_until_ms"] == 10_000 + 300_000
    assert otp_policy.is_locked(state, 10_000 + 299_999) is True
    assert otp_policy.is_locked(state, 10_000 + 300_000) is False


def test_given_two_equal_codes_when_compared_then_a_constant_time_comparison_is_used(monkeypatch):
    calls = []
    import hmac

    real = hmac.compare_digest
    monkeypatch.setattr(otp.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    assert otp.codes_equal("123456", "123456") is True
    assert otp.codes_equal("123456", "654321") is False
    assert len(calls) == 2

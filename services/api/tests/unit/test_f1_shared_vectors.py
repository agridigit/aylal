"""T009 - TS and Python give the same verdicts on the F1 shared vectors."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _load(name: str) -> list[dict]:
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))


def _key(errors: list[dict]) -> list[tuple[str, str]]:
    return sorted((e["field"], e["code"]) for e in errors)


@pytest.mark.parametrize("v", _load("f1_roles.json"), ids=lambda v: f"{v['role']}:{v['action']}")
def test_given_a_role_when_checking_an_action_then_python_matches_the_ts_matrix(v):
    from app.domain.roles import can

    assert can(v["role"], v["action"]) is v["allowed"]


@pytest.mark.parametrize("v", _load("f1_otp_policy.json"), ids=lambda v: v["name"])
def test_given_otp_state_when_applying_policy_then_python_matches_ts(v):
    from app.domain.otp_policy import is_locked, register_failure

    state = {"failed_attempts": v["state"]["failedAttempts"], "locked_until_ms": v["state"]["lockedUntilMs"]}
    if v["action"] == "isLocked":
        assert is_locked(state, v["nowMs"]) is v["expect"]
    else:
        got = register_failure(state, v["nowMs"])
        assert got == {
            "failed_attempts": v["expect"]["failedAttempts"],
            "locked_until_ms": v["expect"]["lockedUntilMs"],
        }


@pytest.mark.parametrize("v", _load("f1_phone.json"), ids=lambda v: v["name"])
def test_given_a_phone_when_validating_then_python_verdict_matches_ts(v):
    from app.generated.validation import validate

    assert validate("phone", {"phone": v["input"]})["valid"] is (v["expect"] is not None)


@pytest.mark.parametrize("v", _load("f1_validation.json"), ids=lambda v: f"{v['rule']}: {v['name']}")
def test_given_farm_consent_profile_input_when_validating_then_python_matches_ts(v):
    from app.generated.validation import validate

    got = validate(v["rule"], v["input"])
    assert got["valid"] is v["expect"]["valid"]
    assert _key(got["errors"]) == _key(v["expect"]["errors"])

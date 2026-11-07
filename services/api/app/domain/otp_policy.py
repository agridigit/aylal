"""OTP lock policy, mirror of packages/domain/src/otp-policy.ts."""
from typing import TypedDict

OTP_MAX_FAILURES = 3
OTP_LOCK_SECONDS = 300


class OtpState(TypedDict):
    failed_attempts: int
    locked_until_ms: int | None


def is_locked(state: OtpState, now_ms: int) -> bool:
    until = state["locked_until_ms"]
    return until is not None and now_ms < until


def register_failure(state: OtpState, now_ms: int) -> OtpState:
    failed = state["failed_attempts"] + 1
    locked = now_ms + OTP_LOCK_SECONDS * 1000 if failed >= OTP_MAX_FAILURES else state["locked_until_ms"]
    return {"failed_attempts": failed, "locked_until_ms": locked}


def is_expired(expires_at_ms: int, now_ms: int) -> bool:
    return now_ms >= expires_at_ms


def attempts_left(state: OtpState) -> int:
    return max(0, OTP_MAX_FAILURES - state["failed_attempts"])

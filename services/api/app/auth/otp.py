"""OTP issuing/checking helpers and the OtpSender port (SMS/WhatsApp adapters plug in here)."""
import hmac
import logging
import secrets
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

TEST_CODE = "000000"
_hasher = PasswordHasher()
log = logging.getLogger("aylal.otp")


class OtpSender(Protocol):
    def send(self, phone_e164: str, code: str, channel: str) -> None: ...


class ConsoleSender:
    """dev/test adapter: never logs the code, only that a send happened."""

    def send(self, phone_e164: str, code: str, channel: str) -> None:
        log.info("otp sent via %s to %s***", channel, phone_e164[:7])


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_code(code: str, pepper: str) -> str:
    return _hasher.hash(pepper + code)


def check_code(code: str, code_hash: str, pepper: str) -> bool:
    try:
        return _hasher.verify(code_hash, pepper + code)
    except (VerificationError, InvalidHashError):
        return False


def codes_equal(a: str, b: str) -> bool:
    """Constant-time comparison of two codes."""
    return hmac.compare_digest(a.encode(), b.encode())

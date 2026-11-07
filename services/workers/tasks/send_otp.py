"""OTP delivery: the OtpSender port, chosen channel first then fallback, Morocco only (R3)."""
import logging
import re
from typing import Any, Protocol

log = logging.getLogger("aylal.send_otp")
_MOROCCO = re.compile(r"\+212[67]\d{8}")
CHANNELS = ("sms", "whatsapp")


class OtpSender(Protocol):
    def send(self, phone_e164: str, code: str, channel: str) -> None: ...


class DeliveryFailed(Exception):
    """Every channel failed."""


class ForeignNumber(Exception):
    """The number is not a Moroccan mobile: no gateway is called."""


def deliver_otp(phone_e164: str, code: str, channel: str, senders: dict[str, OtpSender]) -> str:
    if not _MOROCCO.fullmatch(phone_e164):
        raise ForeignNumber()
    first = channel if channel in CHANNELS else "sms"
    for used in (first, *(c for c in CHANNELS if c != first)):
        sender = senders.get(used)
        if sender is None:
            continue
        try:
            sender.send(phone_e164, code, used)
            return used
        except Exception:  # gateway error: never log the code or the full number
            log.warning("otp delivery failed via %s to %s***", used, phone_e164[:7])
    raise DeliveryFailed()


async def send_otp(ctx: dict[str, Any], phone_e164: str, code: str, channel: str = "sms") -> str:
    senders: dict[str, OtpSender] = ctx.get("senders", {})
    return deliver_otp(phone_e164, code, channel, senders)

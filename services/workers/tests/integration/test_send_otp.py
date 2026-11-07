"""T023 - OtpSender port: chosen channel first, fallback on the other, nothing sent outside Morocco."""
import pytest

from tasks.send_otp import DeliveryFailed, ForeignNumber, deliver_otp


class Fake:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def send(self, phone, code, channel):
        self.calls.append((phone, code, channel))
        if self.fail:
            raise RuntimeError("gateway down")


PHONE = "+212612345678"


def test_given_whatsapp_chosen_when_sending_then_only_whatsapp_is_used():
    sms, wa = Fake(), Fake()
    used = deliver_otp(PHONE, "123456", "whatsapp", {"sms": sms, "whatsapp": wa})
    assert used == "whatsapp" and wa.calls == [(PHONE, "123456", "whatsapp")] and sms.calls == []


def test_given_the_chosen_channel_fails_when_sending_then_the_other_channel_is_tried():
    sms, wa = Fake(fail=True), Fake()
    assert deliver_otp(PHONE, "123456", "sms", {"sms": sms, "whatsapp": wa}) == "whatsapp"
    assert len(sms.calls) == 1 and len(wa.calls) == 1


def test_given_both_channels_fail_when_sending_then_delivery_failed_is_raised():
    with pytest.raises(DeliveryFailed):
        deliver_otp(PHONE, "123456", "sms", {"sms": Fake(True), "whatsapp": Fake(True)})


@pytest.mark.parametrize("phone", ["+33612345678", "+14155550100", "0612345678"])
def test_given_a_number_outside_morocco_when_sending_then_no_gateway_is_called(phone):
    sms, wa = Fake(), Fake()
    with pytest.raises(ForeignNumber):
        deliver_otp(phone, "123456", "sms", {"sms": sms, "whatsapp": wa})
    assert sms.calls == [] and wa.calls == []


def test_given_the_worker_settings_then_send_otp_is_a_registered_task():
    from worker import WorkerSettings

    assert "send_otp" in [f.__name__ for f in WorkerSettings.functions]

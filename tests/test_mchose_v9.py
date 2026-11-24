import pytest

from fakes import FakeFactory, FakeTransport, load_fixture
from monitor_bateria.devices.mchose_v9 import REQUEST, MchoseV9Pro
from monitor_bateria.models import ProtocolError, Status
from monitor_bateria.transport import DeviceNotFound, HidError

FX = load_fixture("mchose_v9")
V100 = FX["valid"][0]["hex"]
OFF = FX["valid"][1]["hex"]


def device(t, timeout=0.3):
    return MchoseV9Pro(FakeFactory(t), read_timeout_s=timeout)


def test_request_matches_capture():
    assert len(REQUEST) == 64 and REQUEST[:3] == bytes([0x55, 0x65, 0x01])
    assert MchoseV9Pro.allowed_report_writes == frozenset({REQUEST})
    assert MchoseV9Pro.allowed_writes == frozenset() and MchoseV9Pro.allowed_feature_writes == frozenset()
    assert MchoseV9Pro.enabled_by_default and not MchoseV9Pro.is_stub


@pytest.mark.parametrize("item", FX["valid"], ids=lambda v: v["nome"])
def test_parse_golden(item):
    assert MchoseV9Pro.parse_response(bytes.fromhex(item["hex"])) == item["percent"]


@pytest.mark.parametrize("item", FX["invalid"], ids=lambda v: v["nome"])
def test_parse_rejects_invalid(item):
    with pytest.raises(ProtocolError):
        MchoseV9Pro.parse_response(bytes.fromhex(item["hex"]))


def test_reads_100_ignoring_connect_notice():
    t = FakeTransport(respond_after_report=FX["noise"] + [V100])
    r = device(t).read()
    assert (r.status, r.percent) == (Status.OK, 100)


def test_sends_exactly_the_numbered_report_and_nothing_else():
    t = FakeTransport(respond_after_report=[V100])
    device(t).read()
    assert t.reports == [REQUEST] and t.written == [] and t.features == []
    assert t.opened and t.closed


def test_stale_notice_before_request_is_discarded():
    t = FakeTransport(reads=[OFF], respond_after_report=[V100])
    assert device(t).read().percent == 100


def test_headset_off_or_usb_mode_is_not_connected():
    assert device(FakeTransport(respond_after_report=[OFF])).read().status is Status.NOT_CONNECTED
    assert device(FakeTransport()).read().status is Status.NOT_CONNECTED      # sem resposta
    assert device(FakeTransport(fail_open=DeviceNotFound("x"))).read().status is Status.NOT_CONNECTED


def test_hid_error_on_write_is_error_not_crash():
    assert device(FakeTransport(fail_report=HidError("x"))).read().status is Status.ERROR

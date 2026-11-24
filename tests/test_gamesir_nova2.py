import pytest

from fakes import FakeFactory, FakeTransport, load_fixture
from monitor_bateria.devices.gamesir_nova2 import CMD_INFO, GameSirNova2
from monitor_bateria.models import ProtocolError, Status
from monitor_bateria.transport import DeviceNotFound, HidError

FX = load_fixture("gamesir_nova2")
VALID = {v["percent"]: v["hex"] for v in FX["valid"]}


def device(transport, timeout=0.3):
    return GameSirNova2(FakeFactory(transport), read_timeout_s=timeout)


@pytest.mark.parametrize("item", FX["valid"], ids=lambda v: v["nome"])
def test_parse_golden_payloads(item):
    assert GameSirNova2.parse_response(bytes.fromhex(item["hex"])) == item["percent"]


@pytest.mark.parametrize("item", FX["invalid"], ids=lambda v: v["nome"])
def test_parse_rejects_invalid(item):
    with pytest.raises(ProtocolError):
        GameSirNova2.parse_response(bytes.fromhex(item["hex"]))


def test_reads_66_skipping_status_stream_noise():
    t = FakeTransport(reads=FX["noise"] + [VALID[66]])
    reading = device(t).read()
    assert (reading.status, reading.percent) == (Status.OK, 66)


def test_sends_exactly_one_whitelisted_frame_and_closes():
    t = FakeTransport(reads=[VALID[66]])
    device(t).read()
    assert t.written == [CMD_INFO] and len(CMD_INFO) == 64
    assert t.opened and t.closed


def test_only_noise_ends_in_timeout():
    t = FakeTransport(reads=FX["noise"] * 3)
    assert device(t, timeout=0.2).read().status is Status.TIMEOUT
    assert t.closed


def test_dongle_absent_is_not_connected():
    t = FakeTransport(fail_open=DeviceNotFound("x"))
    assert device(t).read().status is Status.NOT_CONNECTED
    assert t.closed


def test_zero_percent_means_controller_off():
    t = FakeTransport(reads=[VALID[0]])
    assert device(t).read().status is Status.NOT_CONNECTED


def test_malformed_percent_becomes_error_not_crash():
    bad = next(i["hex"] for i in FX["invalid"] if "100" in i["nome"])
    t = FakeTransport(reads=[bad])
    # o cabeçalho é válido, então o parser roda e rejeita o valor
    assert device(t).read().status is Status.ERROR


def test_comm_failure_becomes_error():
    t = FakeTransport(fail_write=HidError("x"))
    assert device(t).read().status is Status.ERROR
    assert t.closed


def test_targets_the_vendor_interface_only():
    f = FakeFactory(FakeTransport(reads=[VALID[66]]))
    GameSirNova2(f, 0.3).read()
    t = f.targets[0]
    assert (t.vendor_id, t.product_id, t.usage_page) == (0x3537, 0x1098, 0xFF7A)

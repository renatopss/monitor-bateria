import pytest

from fakes import FakeFactory, FakeTransport, load_fixture
from monitor_bateria.devices.mchose_k7 import REQUEST_INFO, MchoseK7Ultra
from monitor_bateria.models import ProtocolError, Status
from monitor_bateria.transport import DeviceNotFound, HidError

FX = load_fixture("mchose_k7")
V93 = next(v["hex"] for v in FX["valid"] if v["percent"] == 93 and "sem carregar" in v["nome"])


def device(t, timeout=0.3):
    return MchoseK7Ultra(FakeFactory(t), read_timeout_s=timeout)


def test_request_matches_capture():
    assert len(REQUEST_INFO) == 21 and REQUEST_INFO[:2] == bytes([0x11, 0xF9])
    assert MchoseK7Ultra.allowed_feature_writes == frozenset({REQUEST_INFO})
    assert MchoseK7Ultra.allowed_writes == frozenset()


def test_default_timeout_is_long_enough_for_the_dongle():
    assert MchoseK7Ultra(FakeFactory(FakeTransport())).default_read_timeout_s >= 6.0
    assert MchoseK7Ultra(FakeFactory(FakeTransport()))._timeout_s >= 6.0


@pytest.mark.parametrize("item", FX["valid"], ids=lambda v: v["nome"])
def test_parse_golden(item):
    assert MchoseK7Ultra.parse_response(bytes.fromhex(item["hex"])) == item["percent"]


@pytest.mark.parametrize("item", FX["invalid"], ids=lambda v: v["nome"])
def test_parse_rejects_invalid(item):
    with pytest.raises(ProtocolError):
        MchoseK7Ultra.parse_response(bytes.fromhex(item["hex"]))


def test_reads_93_ignoring_acks():
    t = FakeTransport(respond_after_feature=FX["noise"] + [V93])
    r = device(t).read()
    assert (r.status, r.percent) == (Status.OK, 93)


def test_sends_only_the_feature_request_and_never_a_plain_write():
    t = FakeTransport(respond_after_feature=[V93])
    device(t).read()
    assert t.features == [REQUEST_INFO] and t.written == []
    assert t.opened and t.closed


def test_stale_packet_before_request_is_discarded():
    stale = next(v["hex"] for v in FX["valid"] if v["percent"] == 96)
    t = FakeTransport(reads=[stale], respond_after_feature=[V93])
    assert device(t).read().percent == 93


def test_only_acks_end_in_timeout():
    t = FakeTransport(respond_after_feature=FX["noise"])
    assert device(t, timeout=0.2).read().status is Status.TIMEOUT


def test_dongle_absent_and_hid_errors():
    assert device(FakeTransport(fail_open=DeviceNotFound("x"))).read().status is Status.NOT_CONNECTED
    assert device(FakeTransport(fail_feature=HidError("x"))).read().status is Status.ERROR


def test_reports_charging_flag():
    on = next(v["hex"] for v in FX["valid"] if "carregando" in v["nome"] and "sem" not in v["nome"])
    assert MchoseK7Ultra.parse_status(bytes.fromhex(on)) == (93, True)
    assert MchoseK7Ultra.parse_status(bytes.fromhex(V93)) == (93, False)
    r = device(FakeTransport(respond_after_feature=[on])).read()
    assert (r.percent, r.charging) == (93, True) and "(carregando)" in r.short()
    r = device(FakeTransport(respond_after_feature=[V93])).read()
    assert r.charging is False and "carregando" not in r.short()


def test_charging_only_allowed_on_ok_readings():
    import pytest as _p
    from monitor_bateria.models import Reading
    with _p.raises(ValueError):
        Reading("a", "A", Status.ERROR, charging=True)
    assert Reading("a", "A", Status.OK, 50).charging is None


# ---- escuta passiva (cabo plugado/removido) -------------------------------
import threading
import time as _time

CHG = next(v for v in FX["valid"] if "carregando" in v["nome"] and "sem carregar" not in v["nome"])


def _run_watch(t, wait=0.4):
    dev = device(t)
    stop, got = threading.Event(), []
    th = threading.Thread(target=dev.watch, args=(stop, got.append), daemon=True)
    th.start()
    _time.sleep(wait)
    stop.set()
    th.join(3)
    assert not th.is_alive()
    return got, t


def test_watch_emits_charging_push_and_never_writes():
    t = FakeTransport(reads=["131a" + "00" * 62, V93, CHG["hex"]])
    got, t = _run_watch(t)
    assert [(r.percent, r.charging) for r in got] == [(93, False), (CHG["percent"], True)]
    assert all(r.status is Status.OK for r in got)
    assert t.features == [] and t.written == [] and t.reports == []


def test_watch_survives_missing_dongle_and_stops():
    got, _ = _run_watch(FakeTransport(fail_open=DeviceNotFound("x")), wait=0.2)
    assert got == []


def test_watch_ignores_garbage_packets():
    got, _ = _run_watch(FakeTransport(reads=["13 1d 00", "13 1d " + "00" * 10]))
    assert got == []

"""Testa o RealHidTransport contra um módulo `hid` falso (sem hardware, sem hidapi)."""
import sys
import types

import pytest

from monitor_bateria.transport import DeviceNotFound, HidError, HidTarget, RealHidTransport

TARGET = HidTarget(0x3537, 0x1098, 0xFF7A)


class FakeDev:
    def __init__(self, log):
        self.log = log
        self.reads = [list(range(64))]

    def open_path(self, path):
        self.log.append(("open", path))

    def write(self, data):
        self.log.append(("write", bytes(data)))
        return len(data)

    def send_feature_report(self, data):
        self.log.append(("feature", bytes(data)))
        return len(data)

    def read(self, size, timeout_ms):
        return self.reads.pop(0) if self.reads else []

    def close(self):
        self.log.append(("close",))


@pytest.fixture
def fake_hid(monkeypatch):
    log = []
    module = types.ModuleType("hid")
    module.enumerate = lambda vid, pid: [
        {"usage_page": 0x0001, "path": b"errado-mouse"},
        {"usage_page": 0xFF7A, "path": b"certo-vendor"},
    ] if (vid, pid) == (0x3537, 0x1098) else []
    module.device = lambda: FakeDev(log)
    monkeypatch.setitem(sys.modules, "hid", module)
    return log


def test_opens_only_the_vendor_interface(fake_hid):
    t = RealHidTransport(TARGET)
    t.open()
    assert fake_hid == [("open", b"certo-vendor")]


def test_write_prefixes_report_id_zero(fake_hid):
    t = RealHidTransport(TARGET)
    t.open()
    t.write(bytes([1, 1]) + bytes(62))
    sent = [e for e in fake_hid if e[0] == "write"][0][1]
    assert len(sent) == 65 and sent[0] == 0x00 and sent[1:3] == bytes([1, 1])


def test_read_returns_bytes_or_none(fake_hid):
    t = RealHidTransport(TARGET)
    t.open()
    assert t.read(64, 10) == bytes(range(64))
    assert t.read(64, 10) is None


def test_missing_device_raises_device_not_found(fake_hid):
    with pytest.raises(DeviceNotFound):
        RealHidTransport(HidTarget(1, 2, 3)).open()


def test_close_is_idempotent_and_blocks_further_io(fake_hid):
    t = RealHidTransport(TARGET)
    t.open()
    t.close()
    t.close()
    assert fake_hid.count(("close",)) == 1
    with pytest.raises(HidError):
        t.write(b"\x01")


def test_missing_hidapi_library_is_a_clean_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "hid", None)  # força ImportError
    with pytest.raises(HidError):
        RealHidTransport(TARGET).open()


def test_feature_report_is_sent_as_is_without_extra_prefix(fake_hid):
    t = RealHidTransport(TARGET)
    t.open()
    t.send_feature_report(bytes([0x11, 0xF9]) + bytes([0xFF]) * 19)
    sent = [e for e in fake_hid if e[0] == "feature"][0][1]
    assert len(sent) == 21 and sent[:2] == bytes([0x11, 0xF9])


def test_numbered_report_is_written_without_extra_prefix(fake_hid):
    t = RealHidTransport(TARGET)
    t.open()
    t.write_report(bytes([0x55, 0x65, 0x01]) + bytes(61))
    sent = [e for e in fake_hid if e[0] == "write"][0][1]
    assert len(sent) == 64 and sent[:3] == bytes([0x55, 0x65, 0x01])

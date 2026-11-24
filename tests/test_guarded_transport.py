import pytest

from fakes import FakeTransport
from monitor_bateria.transport import GuardedTransport, WriteNotAllowed

OK = bytes([1, 1]) + bytes(62)


def test_blocks_non_whitelisted_write():
    inner = FakeTransport()
    g = GuardedTransport(inner, frozenset({OK}))
    with pytest.raises(WriteNotAllowed):
        g.write(b"\x02" + bytes(63))
    assert inner.written == []


def test_allows_whitelisted_write():
    inner = FakeTransport()
    GuardedTransport(inner, frozenset({OK})).write(OK)
    assert inner.written == [OK]


def test_empty_whitelist_blocks_everything():
    inner = FakeTransport()
    with pytest.raises(WriteNotAllowed):
        GuardedTransport(inner, frozenset()).write(OK)
    assert inner.written == []


def test_closes_inner_when_open_fails():
    inner = FakeTransport(fail_open=OSError("x"))
    with pytest.raises(OSError):
        GuardedTransport(inner, frozenset()).open()
    assert inner.closed


def test_feature_reports_have_their_own_whitelist():
    from fakes import FakeTransport
    from monitor_bateria.transport import GuardedTransport, WriteNotAllowed
    ok, bad = bytes([0x11, 0xF9]), bytes([0x11, 0x00])
    inner = FakeTransport()
    g = GuardedTransport(inner, frozenset({b"\x01"}), frozenset({ok}))
    g.send_feature_report(ok)
    with pytest.raises(WriteNotAllowed):
        g.send_feature_report(bad)
    with pytest.raises(WriteNotAllowed):
        g.send_feature_report(b"\x01")  # a lista de write comum não vale para feature
    with pytest.raises(WriteNotAllowed):
        g.write(ok)  # e a de feature não vale para write
    assert inner.features == [ok] and inner.written == []


def test_numbered_reports_have_their_own_whitelist():
    ok = bytes([0x55, 0x65, 0x01]) + bytes(61)
    inner = FakeTransport()
    g = GuardedTransport(inner, frozenset({b"\x01"}), frozenset({b"\x02"}), frozenset({ok}))
    g.write_report(ok)
    for bad in (lambda: g.write_report(b"\x01"), lambda: g.write_report(b"\x02"),
                lambda: g.write(ok), lambda: g.send_feature_report(ok)):
        with pytest.raises(WriteNotAllowed):
            bad()
    assert inner.reports == [ok] and inner.written == [] and inner.features == []

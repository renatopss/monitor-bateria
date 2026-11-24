"""CONTRATO: vale para TODO plugin registrado, inclusive os futuros (mouse/headset).

Quando um plugin novo entra em ALL_DEVICE_CLASSES, estes testes passam a rodar
nele automaticamente. Nenhum teste precisa ser editado.
"""
import time

import pytest

from fakes import CHAOS, ChaosTransport, FakeFactory, FakeTransport, load_fixture
from monitor_bateria.devices import ALL_DEVICE_CLASSES
from monitor_bateria.devices.base import BatteryDevice, UnsupportedDevice
from monitor_bateria.models import ProtocolError, Reading, Status
from monitor_bateria.transport import HidTarget

IDS = [c.device_id for c in ALL_DEVICE_CLASSES]
REAL = [c for c in ALL_DEVICE_CLASSES if not c.is_stub]
STUBS = [c for c in ALL_DEVICE_CLASSES if c.is_stub]


def build(cls, transport):
    return cls(FakeFactory(transport), read_timeout_s=0.2)


def test_registry_is_consistent():
    assert len(set(IDS)) == len(IDS), "device_id duplicado"
    assert all(i and i == i.lower().replace(" ", "_") for i in IDS)


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=IDS)
def test_class_metadata(cls):
    assert issubclass(cls, BatteryDevice)
    assert cls.name and isinstance(cls.target, HidTarget)
    assert isinstance(cls.allowed_writes, frozenset)
    assert all(isinstance(w, bytes) and 0 < len(w) <= 64 for w in cls.allowed_writes)


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=IDS)
@pytest.mark.parametrize("exc", CHAOS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("where", ["open", "write", "read"])
def test_read_never_raises_whatever_the_transport_does(cls, exc, where):
    reading = build(cls, ChaosTransport(exc, where)).read()
    assert isinstance(reading, Reading)
    assert reading.device_id == cls.device_id and reading.device_name == cls.name


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=IDS)
def test_read_is_bounded_in_time_when_device_is_silent(cls):
    start = time.monotonic()
    build(cls, FakeTransport()).read()
    assert time.monotonic() - start < 2.0


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=IDS)
def test_only_whitelisted_bytes_reach_the_hardware(cls):
    t = FakeTransport()
    build(cls, t).read()
    assert all(w in cls.allowed_writes for w in t.written)


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=IDS)
def test_transport_is_always_closed(cls):
    t = FakeTransport()
    build(cls, t).read()
    assert t.closed or not t.opened


# ---- plugins reais: fixtures douradas são OBRIGATÓRIAS ----------------------

@pytest.mark.parametrize("cls", REAL, ids=[c.device_id for c in REAL])
def test_real_plugins_have_golden_fixtures(cls):
    fx = load_fixture(cls.device_id)  # falha se o arquivo não existir
    assert fx["valid"] and fx["invalid"], "fixture precisa de casos válidos e inválidos"
    for item in fx["valid"]:
        assert cls.parse_response(bytes.fromhex(item["hex"])) == item["percent"]
    for item in fx["invalid"]:
        with pytest.raises(ProtocolError):
            cls.parse_response(bytes.fromhex(item["hex"]))


# ---- plugins reservados: continuam inofensivos ----------------------------

@pytest.mark.parametrize("cls", STUBS, ids=[c.device_id for c in STUBS])
def test_stubs_never_touch_hardware_and_stay_off_by_default(cls):
    t = FakeTransport()
    f = FakeFactory(t)
    reading = cls(f).read()
    assert reading.status is Status.UNSUPPORTED
    assert not f.targets and not t.opened and not t.written
    assert cls.enabled_by_default is False and issubclass(cls, UnsupportedDevice)

"""CENÁRIO: o dia em que descobrirmos a bateria do mouse e do headset.

Simula o plugin novo entrando no app e prova três coisas:
  1. o controle continua lendo exatamente igual (nenhuma regressão);
  2. um plugin novo com bug (erro, travamento ou comando proibido) não derruba nada;
  3. o próprio plugin novo obedece ao mesmo contrato dos demais.
Para o mouse/headset reais: troque FakeMouse pelo plugin e a fixture pela captura real.
"""
import time
from typing import ClassVar

import pytest

from fakes import CHAOS, ChaosTransport, FakeFactory, FakeTransport, load_fixture
from monitor_bateria.devices import ALL_DEVICE_CLASSES, GameSirNova2
from monitor_bateria.devices.base import BatteryDevice
from monitor_bateria.models import ProtocolError, Status
from monitor_bateria.service import MonitorService
from monitor_bateria.transport import HidTarget

FX = load_fixture("gamesir_nova2")
GOLDEN_66 = next(v["hex"] for v in FX["valid"] if v["percent"] == 66)

MOUSE_CMD = bytes([0x11, 0x06]) + bytes(62)


class FakeMouse(BatteryDevice):
    """Plugin hipotético: comando + resposta `22 <pct>` (formato inventado)."""
    device_id: ClassVar[str] = "fake_mouse"
    name: ClassVar[str] = "Mouse (teste)"
    target: ClassVar[HidTarget] = HidTarget(0x5253, 0x1020, 0xFF01)
    allowed_writes: ClassVar[frozenset[bytes]] = frozenset({MOUSE_CMD})

    @classmethod
    def parse_response(cls, data):
        if len(data) < 2 or data[0] != 0x22 or data[1] > 100:
            raise ProtocolError("formato inesperado")
        return data[1]

    def _read_percent(self, transport):
        transport.write(MOUSE_CMD)
        for _ in range(10):
            data = transport.read(64, 50)
            if data and data[0] == 0x22:
                return self.parse_response(data)
        from monitor_bateria.models import ResponseTimeout
        raise ResponseTimeout()


class BuggyForbiddenWrite(FakeMouse):
    device_id: ClassVar[str] = "buggy_write"

    def _read_percent(self, transport):
        transport.write(bytes([0xFF]) + bytes(63))  # fora da lista permitida
        return 50


class BuggyHang(FakeMouse):
    device_id: ClassVar[str] = "buggy_hang"

    def read(self):
        time.sleep(5)


class BuggyRaises(FakeMouse):
    device_id: ClassVar[str] = "buggy_raises"

    def read(self):
        raise RuntimeError("bug no plugin novo")


def gamesir():
    t = FakeTransport(reads=FX["noise"] + [GOLDEN_66])
    return GameSirNova2(FakeFactory(t), read_timeout_s=0.3)


def mouse(cls=FakeMouse, reads=("22" + "4b" + "00" * 62,)):
    t = FakeTransport(reads=reads)
    return cls(FakeFactory(t), read_timeout_s=0.3), t


def test_adding_a_plugin_does_not_change_the_controller_reading():
    alone = MonitorService([gamesir()], 60, 20).poll_once()
    together = MonitorService([gamesir(), mouse()[0]], 60, 20).poll_once()
    assert together[0] == alone[0] and alone[0].percent == 66
    assert (together[1].status, together[1].percent) == (Status.OK, 75)


def test_buggy_new_plugins_are_contained():
    forbidden, t_forbidden = mouse(BuggyForbiddenWrite)
    svc = MonitorService(
        [gamesir(), forbidden, mouse(BuggyHang)[0], mouse(BuggyRaises)[0]],
        60, 20, device_timeout_s=0.3,
    )
    by_id = {r.device_id: r for r in svc.poll_once()}
    assert by_id["gamesir_nova2"].percent == 66            # controle intacto
    assert by_id["buggy_write"].status is Status.ERROR      # comando proibido barrado
    assert t_forbidden.written == []                        # nada chegou ao hardware
    assert by_id["buggy_hang"].status is Status.TIMEOUT
    assert by_id["buggy_raises"].status is Status.ERROR


def test_new_plugin_reads_and_respects_whitelist():
    device, transport = mouse()
    reading = device.read()
    assert (reading.status, reading.percent) == (Status.OK, 75)
    assert transport.written == [MOUSE_CMD] and transport.closed


def test_new_plugin_rejects_malformed_payloads():
    # cabeçalho certo, valor absurdo (255%): erro
    device, _ = mouse(reads=("22" + "ff" + "00" * 62,))
    assert device.read().status is Status.ERROR
    # cabeçalho desconhecido: tratado como ruído do fluxo, acaba em timeout
    device, _ = mouse(reads=("99" + "10" + "00" * 62,))
    assert device.read().status is Status.TIMEOUT


@pytest.mark.parametrize("exc", CHAOS, ids=lambda e: type(e).__name__)
@pytest.mark.parametrize("where", ["open", "write", "read"])
def test_new_plugin_survives_transport_chaos(exc, where):
    reading = FakeMouse(FakeFactory(ChaosTransport(exc, where)), 0.2).read()
    assert reading.device_id == "fake_mouse"


def test_new_plugin_has_unique_id_and_is_not_registered_by_accident():
    ids = [c.device_id for c in ALL_DEVICE_CLASSES]
    assert "fake_mouse" not in ids          # o fake só existe nos testes
    assert FakeMouse.device_id not in ids

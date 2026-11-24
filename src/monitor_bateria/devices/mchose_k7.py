"""Mouse Mchose K7 Ultra via receptor 2.4G (VID 5253, PID 1020).

Protocolo observado nas capturas do M HUB (cap2 e cap4) e confirmado ao vivo:
  - pedido: feature report de 21 bytes `11 f9 ff*19` na interface vendor 0xFF01
    (é o "ler informações" do M HUB; os bytes de dados vêm invertidos, 0xF9 = ~0x06);
  - cerca de 2 s depois o receptor empurra um pacote de entrada `13 1d ...`,
    também invertido bit a bit. Desinvertido: `01 01 <carregando> <bateria> 02 04 06 "(K7 Ultra"`;
  - byte 4 do pacote cru: 0xFE = carregando, 0xFF = não; byte 5: bateria = 255 - valor.
O pacote também aparece sozinho em eventos (cabo plugado/removido). Pacotes `13 1a`
são só confirmações dos pedidos e são ignorados.
Confirmado: valor 93% (M HUB arredonda para a dezena, mostrava 90%).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, ClassVar

from ..models import ProtocolError, Reading, ResponseTimeout, Status
from ..transport import GuardedTransport, HidError, HidTarget
from .base import BatteryDevice

log = logging.getLogger(__name__)

REQUEST_INFO = bytes([0x11, 0xF9]) + bytes([0xFF]) * 19
STATUS_HEADER = bytes([0x13, 0x1D])
MIN_STATUS_LEN = 6
CHARGING_OFFSET = 4
BATTERY_OFFSET = 5


class MchoseK7Ultra(BatteryDevice):
    icon_kind: ClassVar[str] = "mouse"
    supports_push: ClassVar[bool] = True
    device_id: ClassVar[str] = "mchose_k7"
    name: ClassVar[str] = "Mouse Mchose K7"
    target: ClassVar[HidTarget] = HidTarget(0x5253, 0x1020, 0xFF01)
    allowed_feature_writes: ClassVar[frozenset[bytes]] = frozenset({REQUEST_INFO})
    default_read_timeout_s: ClassVar[float] = 8.0  # o receptor leva ~2 s (até ~5,5 s) para responder

    @classmethod
    def parse_response(cls, data: bytes) -> int:
        return cls.parse_status(data)[0]

    @classmethod
    def parse_status(cls, data: bytes) -> tuple[int, bool]:
        """(bateria %, carregando)."""
        if len(data) < MIN_STATUS_LEN:
            raise ProtocolError("resposta curta demais")
        if data[:2] != STATUS_HEADER:
            raise ProtocolError("cabeçalho inesperado")
        if data[CHARGING_OFFSET] not in (0xFE, 0xFF):
            raise ProtocolError("flag de carga inesperada")
        percent = 255 - data[BATTERY_OFFSET]
        if percent > 100:
            raise ProtocolError("bateria fora de 0-100")
        return percent, data[CHARGING_OFFSET] == 0xFE

    def _read_percent(self, transport: GuardedTransport) -> tuple[int, bool]:
        # Limpa pacotes velhos para não confundir com a resposta deste pedido.
        for _ in range(64):
            if not transport.read(64, 1):
                break
        transport.send_feature_report(REQUEST_INFO)
        deadline = time.monotonic() + self._timeout_s
        while time.monotonic() < deadline:
            data = transport.read(64, 200)
            if not data or data[:2] != STATUS_HEADER:
                continue  # confirmação 13 1a ou outro pacote: ignora
            return self.parse_status(data)
        raise ResponseTimeout()

    def watch(self, stop: threading.Event, emit: Callable[[Reading], None]) -> None:
        """Escuta os pacotes `13 1d` que o receptor empurra (cabo plugado/removido).

        Somente leitura: não envia nada ao mouse. read() bloqueia até 1 s, então o
        custo de CPU é praticamente zero. Se o receptor some, tenta de novo com espera.
        """
        backoff = 5.0
        while not stop.is_set():
            try:
                with self._open() as transport:
                    backoff = 5.0
                    while not stop.is_set():
                        data = transport.read(64, 1000)
                        if not data or data[:2] != STATUS_HEADER:
                            continue
                        try:
                            percent, charging = self.parse_status(data)
                        except ProtocolError:
                            continue
                        emit(self._result(Status.OK, percent, charging=charging))
            except (HidError, OSError):
                pass  # receptor ausente/removido: espera e tenta de novo
            except Exception:  # noqa: BLE001
                log.exception("escuta do %s falhou", self.device_id)
            stop.wait(backoff)
            backoff = min(backoff * 2, 60.0)

"""Controle GameSir Nova 2 (Lite) via dongle 2.4G (VID 3537, PID 1098).

Protocolo observado nas capturas USB do GameSir Connect:
  - o app envia um pacote de 64 bytes `01 01 00 ...` na interface vendor 0xFF7A;
  - o dongle responde `01 85 ...` e o byte 18 é a bateria em %;
  - entre uma coisa e outra o dongle manda um fluxo contínuo de pacotes
    de estado (começam com f4/f3/21 ...), que devem ser ignorados.
Confirmado com 66% no app (byte = 0x42). Só a leitura é feita.
"""
from __future__ import annotations

import time
from typing import ClassVar

from ..models import NoReading, ProtocolError, ResponseTimeout
from ..transport import GuardedTransport, HidTarget
from .base import BatteryDevice

CMD_INFO = bytes([0x01, 0x01]) + bytes(62)
RESPONSE_HEADER = bytes([0x01, 0x85])
BATTERY_OFFSET = 18


class GameSirNova2(BatteryDevice):
    icon_kind: ClassVar[str] = "controller"
    device_id: ClassVar[str] = "gamesir_nova2"
    name: ClassVar[str] = "Controle GameSir"
    target: ClassVar[HidTarget] = HidTarget(0x3537, 0x1098, 0xFF7A)
    allowed_writes: ClassVar[frozenset[bytes]] = frozenset({CMD_INFO})

    @classmethod
    def parse_response(cls, data: bytes) -> int:
        if len(data) <= BATTERY_OFFSET:
            raise ProtocolError("resposta curta demais")
        if data[:2] != RESPONSE_HEADER:
            raise ProtocolError("cabeçalho inesperado")
        percent = data[BATTERY_OFFSET]
        if percent > 100:
            raise ProtocolError("bateria fora de 0-100")
        return percent

    def _read_percent(self, transport: GuardedTransport) -> int:
        transport.write(CMD_INFO)
        deadline = time.monotonic() + self._timeout_s
        while time.monotonic() < deadline:
            data = transport.read(64, 200)
            if not data or data[:2] != RESPONSE_HEADER:
                continue  # pacote do fluxo de estado: ignora
            percent = self.parse_response(data)
            if percent == 0:
                raise NoReading("leitura 0%: controle desligado?")
            return percent
        raise ResponseTimeout()

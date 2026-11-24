"""Headset Mchose V9 Pro via dongle 2.4G (VID 291D, PID 385D), coleção HID 0xFF90.

Protocolo visto na captura do M HUB (cap5) e confirmado ao vivo:
  - pedido: relatório de saída de 64 bytes `55 65 01 00...` (o 0x55 é o report ID, vai como está);
  - ~40 ms depois o dongle responde `55 65 <bateria> <estado> 00...`; byte 2 = bateria em %
    (0x64 = 100%) e estado 0x02 quando conectado;
  - `55 65 00 1a` = headset fora do 2.4G (ligado o cabo de carga ele vira modo USB e sai do dongle);
  - `55 11 01 00` = aviso de "conectou"; é ignorado aqui.
O headset não informa "carregando": ao plugar o cabo ele some do 2.4G.
Confirmado só com 100% (a bateria nunca estava abaixo disso nas capturas).
"""
from __future__ import annotations

import time
from typing import ClassVar

from ..models import NoReading, ProtocolError
from ..transport import GuardedTransport, HidTarget
from .base import BatteryDevice

REQUEST = bytes([0x55, 0x65, 0x01]) + bytes(61)
RESPONSE_HEADER = bytes([0x55, 0x65])
BATTERY_OFFSET = 2
MIN_LEN = 4


class MchoseV9Pro(BatteryDevice):
    icon_kind: ClassVar[str] = "headset"
    device_id: ClassVar[str] = "mchose_v9"
    name: ClassVar[str] = "Headset Mchose V9"
    target: ClassVar[HidTarget] = HidTarget(0x291D, 0x385D, 0xFF90)
    allowed_report_writes: ClassVar[frozenset[bytes]] = frozenset({REQUEST})
    default_read_timeout_s: ClassVar[float] = 3.0

    @classmethod
    def parse_response(cls, data: bytes) -> int:
        if len(data) < MIN_LEN:
            raise ProtocolError("resposta curta demais")
        if data[:2] != RESPONSE_HEADER:
            raise ProtocolError("cabeçalho inesperado")
        percent = data[BATTERY_OFFSET]
        if percent > 100:
            raise ProtocolError("bateria fora de 0-100")
        return percent

    def _read_percent(self, transport: GuardedTransport) -> int:
        for _ in range(64):  # descarta avisos antigos (ex.: 55 11 01)
            if not transport.read(64, 1):
                break
        transport.write_report(REQUEST)
        deadline = time.monotonic() + self._timeout_s
        while time.monotonic() < deadline:
            data = transport.read(64, 200)
            if not data or data[:2] != RESPONSE_HEADER:
                continue
            percent = self.parse_response(data)
            if percent == 0:
                raise NoReading("headset fora do 2.4G (desligado ou carregando em USB)")
            return percent
        raise NoReading("sem resposta: headset desligado ou fora do 2.4G")

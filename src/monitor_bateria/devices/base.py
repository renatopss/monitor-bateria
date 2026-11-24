"""Contrato que todo plugin de dispositivo segue.

`read()` NUNCA levanta exceção: sempre devolve um Reading. Cada plugin só
implementa `_read_percent()` (e `parse_response()`); o tratamento de erros,
o fechamento do transporte e o bloqueio de escritas ficam aqui, no base.
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Callable, ClassVar

from ..models import NoReading, ProtocolError, Reading, ResponseTimeout, Status
from ..transport import (
    DeviceNotFound,
    GuardedTransport,
    HidError,
    HidTarget,
    TransportFactory,
)

log = logging.getLogger(__name__)


class BatteryDevice(ABC):
    device_id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    target: ClassVar[HidTarget]
    # Únicos comandos que este plugin pode escrever no aparelho.
    allowed_writes: ClassVar[frozenset[bytes]] = frozenset()
    # Únicos feature reports que este plugin pode enviar (lista separada).
    allowed_feature_writes: ClassVar[frozenset[bytes]] = frozenset()
    # Únicos relatórios numerados (report ID já no 1º byte) que este plugin pode escrever.
    allowed_report_writes: ClassVar[frozenset[bytes]] = frozenset()
    # Tempo máximo esperando o aparelho responder (plugins lentos sobrescrevem).
    default_read_timeout_s: ClassVar[float] = 2.0
    enabled_by_default: ClassVar[bool] = True
    is_stub: ClassVar[bool] = False
    icon_kind: ClassVar[str] = ""  # controller | mouse | headset
    # True se o aparelho avisa sozinho (cabo plugado etc.) e o plugin implementa watch().
    supports_push: ClassVar[bool] = False
    def __init__(self, transport_factory: TransportFactory, read_timeout_s: float | None = None):
        self._factory = transport_factory
        self._timeout_s = self.default_read_timeout_s if read_timeout_s is None else read_timeout_s

    @classmethod
    def parse_response(cls, data: bytes) -> int:
        """Converte um pacote do aparelho em % (0-100). Levanta ProtocolError."""
        raise NotImplementedError

    @abstractmethod
    def _read_percent(self, transport: GuardedTransport) -> "int | tuple[int, bool | None]":
        """Fala com o aparelho e devolve a % de bateria (ou (%, carregando) se ele informar)."""

    def watch(self, stop: threading.Event, emit: Callable[[Reading], None]) -> None:
        """Escuta avisos espontâneos do aparelho (somente leitura) até `stop`."""
        raise NotImplementedError

    def _open(self) -> GuardedTransport:
        guarded = GuardedTransport(
            self._factory(self.target), self.allowed_writes, self.allowed_feature_writes,
            self.allowed_report_writes,
        )
        guarded.open()
        return guarded

    def _result(
        self, status: Status, percent: int | None = None, detail: str = "", charging: bool | None = None
    ) -> Reading:
        return Reading(self.device_id, self.name, status, percent, detail, charging)

    def read(self) -> Reading:
        try:
            with self._open() as transport:
                result = self._read_percent(transport)
            if isinstance(result, tuple):
                percent, charging = result
                return self._result(Status.OK, percent, charging=charging)
            return self._result(Status.OK, result)
        except DeviceNotFound:
            return self._result(Status.NOT_CONNECTED, detail="dongle não encontrado")
        except NoReading as exc:
            return self._result(Status.NOT_CONNECTED, detail=str(exc)[:80])
        except ResponseTimeout:
            return self._result(Status.TIMEOUT, detail="sem resposta do aparelho")
        except ProtocolError as exc:
            return self._result(Status.ERROR, detail=str(exc)[:80])
        except (HidError, OSError):
            return self._result(Status.ERROR, detail="falha de comunicação")
        except Exception:  # noqa: BLE001 - o contrato é nunca propagar
            log.exception("falha interna no plugin %s", self.device_id)
            return self._result(Status.ERROR, detail="falha interna")


class UnsupportedDevice(BatteryDevice):
    """Plugin reservado: o protocolo ainda não foi decifrado.

    Não abre o aparelho, não escreve nada. Fica desligado por padrão.
    Quando o protocolo for descoberto, troque a herança para BatteryDevice,
    implemente `_read_percent`/`parse_response` e crie a fixture em
    tests/fixtures/<device_id>.json (o teste de contrato exige).
    """

    is_stub: ClassVar[bool] = True
    enabled_by_default: ClassVar[bool] = False

    def _read_percent(self, transport: GuardedTransport) -> int:  # pragma: no cover
        raise NotImplementedError

    def read(self) -> Reading:
        return self._result(Status.UNSUPPORTED, detail="protocolo ainda não decifrado")

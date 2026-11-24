"""Tipos de dados compartilhados. Sem dependências externas."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    OK = "ok"
    NOT_CONNECTED = "nao_conectado"
    UNSUPPORTED = "nao_suportado"
    TIMEOUT = "timeout"
    ERROR = "erro"


class ProtocolError(Exception):
    """A resposta do aparelho não tem o formato esperado."""


class NoReading(Exception):
    """O aparelho respondeu, mas sem uma leitura de bateria utilizável."""


class ResponseTimeout(Exception):
    """O aparelho não respondeu dentro do prazo."""


@dataclass(frozen=True)
class Reading:
    device_id: str
    device_name: str
    status: Status
    percent: int | None = None
    detail: str = ""
    charging: bool | None = None  # None = o aparelho não informa

    def __post_init__(self) -> None:
        if self.status is Status.OK:
            ok = (
                isinstance(self.percent, int)
                and not isinstance(self.percent, bool)
                and 0 <= self.percent <= 100
            )
            if not ok:
                raise ValueError("leitura OK exige percent inteiro entre 0 e 100")
        elif self.percent is not None:
            raise ValueError("percent só pode existir quando o status é OK")
        if self.charging is not None and (not isinstance(self.charging, bool) or self.status is not Status.OK):
            raise ValueError("charging só vale em leitura OK e deve ser booleano")

    def short(self) -> str:
        if self.status is Status.OK:
            suffix = " (carregando)" if self.charging else ""
            return f"{self.device_name}: {self.percent}%{suffix}"
        labels = {
            Status.NOT_CONNECTED: "desconectado",
            Status.UNSUPPORTED: "sem suporte ainda",
            Status.TIMEOUT: "sem resposta",
            Status.ERROR: "erro",
        }
        return f"{self.device_name}: {labels[self.status]}"

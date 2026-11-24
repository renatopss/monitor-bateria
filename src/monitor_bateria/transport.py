"""Acesso ao HID. É o ÚNICO módulo que importa a biblioteca `hid`.

Segurança: todo plugin só recebe um GuardedTransport, que recusa qualquer
escrita fora da lista de comandos que o próprio plugin declarou.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class HidError(Exception):
    """Falha de comunicação com o aparelho."""


class DeviceNotFound(HidError):
    """O dongle/aparelho não está presente."""


class WriteNotAllowed(HidError):
    """Tentativa de enviar um comando que não está na lista permitida."""


@dataclass(frozen=True)
class HidTarget:
    vendor_id: int
    product_id: int
    usage_page: int


class Transport(Protocol):
    def open(self) -> None: ...
    def write(self, data: bytes) -> None: ...
    def send_feature_report(self, data: bytes) -> None: ...
    def write_report(self, data: bytes) -> None: ...
    def read(self, size: int, timeout_ms: int) -> bytes | None: ...
    def close(self) -> None: ...


TransportFactory = Callable[[HidTarget], Transport]


class GuardedTransport:
    """Envolve um Transport e só deixa passar escritas da lista permitida."""

    def __init__(
        self,
        inner: Transport,
        allowed_writes: frozenset[bytes],
        allowed_feature_writes: frozenset[bytes] = frozenset(),
        allowed_report_writes: frozenset[bytes] = frozenset(),
    ) -> None:
        self._inner = inner
        self._allowed = allowed_writes
        self._allowed_feature = allowed_feature_writes
        self._allowed_report = allowed_report_writes

    def open(self) -> None:
        try:
            self._inner.open()
        except BaseException:
            self._inner.close()
            raise

    def write(self, data: bytes) -> None:
        payload = bytes(data)
        if payload not in self._allowed:
            raise WriteNotAllowed("comando fora da lista permitida")
        self._inner.write(payload)

    def write_report(self, data: bytes) -> None:
        payload = bytes(data)
        if payload not in self._allowed_report:
            raise WriteNotAllowed("relatório fora da lista permitida")
        self._inner.write_report(payload)

    def send_feature_report(self, data: bytes) -> None:
        payload = bytes(data)
        if payload not in self._allowed_feature:
            raise WriteNotAllowed("feature report fora da lista permitida")
        self._inner.send_feature_report(payload)

    def read(self, size: int, timeout_ms: int) -> bytes | None:
        return self._inner.read(size, timeout_ms)

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> "GuardedTransport":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class RealHidTransport:
    """Implementação real, via hidapi. Abre só a interface pedida (usage page)."""

    def __init__(self, target: HidTarget) -> None:
        self._target = target
        self._dev = None

    def open(self) -> None:
        try:
            import hid  # importação tardia: só aqui
        except ImportError as exc:
            raise HidError("biblioteca hidapi não instalada") from exc

        t = self._target
        path = None
        for info in hid.enumerate(t.vendor_id, t.product_id):
            if info.get("usage_page") == t.usage_page:
                path = info["path"]
                break
        if path is None:
            raise DeviceNotFound("interface HID não encontrada")
        dev = hid.device()
        try:
            dev.open_path(path)
        except OSError as exc:
            raise HidError("não foi possível abrir a interface HID") from exc
        self._dev = dev

    def write(self, data: bytes) -> None:
        if self._dev is None:
            raise HidError("transporte fechado")
        # Relatório sem ID numerado: o hidapi exige o byte 0x00 na frente.
        written = self._dev.write(b"\x00" + bytes(data))
        if written is None or written < 0:
            raise HidError("falha ao escrever no aparelho")

    def write_report(self, data: bytes) -> None:
        if self._dev is None:
            raise HidError("transporte fechado")
        # Relatório NUMERADO: o primeiro byte de `data` já é o report ID (nada é acrescentado).
        written = self._dev.write(bytes(data))
        if written is None or written < 0:
            raise HidError("falha ao escrever relatório")

    def send_feature_report(self, data: bytes) -> None:
        if self._dev is None:
            raise HidError("transporte fechado")
        # `data` já começa pelo report ID (0x11), como o hidapi espera.
        written = self._dev.send_feature_report(bytes(data))
        if written is None or written < 0:
            raise HidError("falha ao enviar feature report")

    def read(self, size: int, timeout_ms: int) -> bytes | None:
        if self._dev is None:
            raise HidError("transporte fechado")
        data = self._dev.read(size, timeout_ms)
        return bytes(data) if data else None

    def close(self) -> None:
        dev, self._dev = self._dev, None
        if dev is not None:
            try:
                dev.close()
            except OSError:
                pass


def real_transport_factory(target: HidTarget) -> Transport:
    return RealHidTransport(target)


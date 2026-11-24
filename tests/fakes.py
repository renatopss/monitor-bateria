"""Aparelhos e transportes falsos para testar sem hardware."""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path

from monitor_bateria.transport import HidError

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(device_id: str) -> dict:
    return json.loads((FIXTURES / f"{device_id}.json").read_text(encoding="utf-8"))


class FakeTransport:
    """Transporte roteirizado: devolve `reads` em ordem e grava tudo que foi escrito."""

    def __init__(self, reads=(), fail_open: Exception | None = None,
                 fail_write: Exception | None = None, fail_read: Exception | None = None,
                 respond_after_write: list[bytes] | None = None,
                 respond_after_feature: list[bytes] | None = None,
                 fail_feature: Exception | None = None,
                 respond_after_report: list | None = None,
                 fail_report: Exception | None = None):
        self.reads = deque(bytes.fromhex(r) if isinstance(r, str) else r for r in reads)
        self.respond_after_write = respond_after_write
        self.respond_after_feature = respond_after_feature
        self.fail_feature = fail_feature
        self.features: list[bytes] = []
        self.reports: list[bytes] = []
        self.respond_after_report = respond_after_report
        self.fail_report = fail_report
        self.fail_open, self.fail_write, self.fail_read = fail_open, fail_write, fail_read
        self.written: list[bytes] = []
        self.opened = False
        self.closed = False

    def open(self):
        if self.fail_open:
            raise self.fail_open
        self.opened = True

    def write(self, data):
        if self.fail_write:
            raise self.fail_write
        self.written.append(bytes(data))
        if self.respond_after_write is not None:
            self.reads.extend(self.respond_after_write)

    def write_report(self, data):
        if self.fail_report:
            raise self.fail_report
        self.reports.append(bytes(data))
        if self.respond_after_report is not None:
            self.reads.extend(bytes.fromhex(r) if isinstance(r, str) else r
                              for r in self.respond_after_report)

    def send_feature_report(self, data):
        if self.fail_feature:
            raise self.fail_feature
        self.features.append(bytes(data))
        if self.respond_after_feature is not None:
            self.reads.extend(bytes.fromhex(r) if isinstance(r, str) else r
                              for r in self.respond_after_feature)

    def read(self, size, timeout_ms):
        if self.fail_read:
            raise self.fail_read
        if self.reads:
            return self.reads.popleft()
        time.sleep(0.005)  # simula a espera do timeout sem demorar o teste
        return None

    def close(self):
        self.closed = True


class FakeFactory:
    """Entrega sempre o mesmo FakeTransport e guarda o alvo pedido."""

    def __init__(self, transport: FakeTransport):
        self.transport = transport
        self.targets = []

    def __call__(self, target):
        self.targets.append(target)
        return self.transport


class ChaosTransport(FakeTransport):
    """Falha de um jeito escolhido, para provar que nada vaza do plugin."""

    def __init__(self, exc: Exception, where: str):
        super().__init__(
            fail_open=exc if where == "open" else None,
            fail_write=exc if where == "write" else None,
            fail_feature=exc if where == "write" else None,
            fail_report=exc if where == "write" else None,
            fail_read=exc if where == "read" else None,
        )


CHAOS = [
    HidError("x"), OSError("x"), ValueError("x"), RuntimeError("x"),
    KeyError("x"), MemoryError(), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "x"),
]

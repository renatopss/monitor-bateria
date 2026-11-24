"""Laço de leitura: uma thread dormindo, acorda a cada N minutos."""
from __future__ import annotations

import logging
import threading
from typing import Callable, Sequence

from .devices.base import BatteryDevice
from .models import Reading, Status

log = logging.getLogger(__name__)

RECOVERY_MARGIN = 10  # o alerta só rearma depois de subir 10 pontos acima do limite


def run_with_timeout(fn: Callable[[], Reading], timeout_s: float) -> Reading:
    """Roda fn numa thread daemon; se travar, a leitura é descartada."""
    box: dict[str, object] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        raise TimeoutError
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box["value"]  # type: ignore[return-value]


class AlertTracker:
    """Avisa uma única vez quando a bateria cai até o limite (com histerese)."""

    def __init__(self, low_percent: int) -> None:
        self._low = low_percent
        self._alerted: set[str] = set()

    def should_alert(self, reading: Reading) -> bool:
        if reading.status is not Status.OK or reading.percent is None or reading.charging:
            return False
        if reading.percent <= self._low:
            if reading.device_id in self._alerted:
                return False
            self._alerted.add(reading.device_id)
            return True
        if reading.percent >= self._low + RECOVERY_MARGIN:
            self._alerted.discard(reading.device_id)
        return False


class MonitorService:
    def __init__(
        self,
        devices: Sequence[BatteryDevice],
        interval_s: float,
        low_percent: int,
        on_update: Callable[[list[Reading]], None] | None = None,
        on_alert: Callable[[Reading], None] | None = None,
        device_timeout_s: float = 15.0,
        pause_when: Callable[[], bool] | None = None,
        pause_retry_s: float = 60.0,
    ) -> None:
        self._devices = list(devices)
        self._interval_s = interval_s
        self._alerts = AlertTracker(low_percent)
        self._on_update = on_update
        self._on_alert = on_alert
        self._device_timeout_s = device_timeout_s
        self._pause_when = pause_when      # ex.: jogo em tela cheia -> não lê nada
        self._pause_retry_s = pause_retry_s
        self._forced = False
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._watchers: list[threading.Thread] = []
        self._latest: list[Reading] = []
        self._lock = threading.Lock()

    def set_callbacks(self, on_update=None, on_alert=None) -> None:
        """Liga a interface depois de criada (chamar antes de start())."""
        self._on_update = on_update
        self._on_alert = on_alert

    @property
    def devices(self) -> list[BatteryDevice]:
        return list(self._devices)

    @property
    def latest(self) -> list[Reading]:
        with self._lock:
            return list(self._latest)

    def _read_device(self, device: BatteryDevice) -> Reading:
        try:
            reading = run_with_timeout(device.read, self._device_timeout_s)
        except TimeoutError:
            return Reading(device.device_id, device.name, Status.TIMEOUT, detail="plugin travou")
        except Exception:  # noqa: BLE001
            log.exception("plugin %s levantou exceção", device.device_id)
            return Reading(device.device_id, device.name, Status.ERROR, detail="falha interna")
        if not isinstance(reading, Reading) or reading.device_id != device.device_id:
            return Reading(device.device_id, device.name, Status.ERROR, detail="resposta inválida do plugin")
        return reading

    def poll_once(self) -> list[Reading]:
        readings = [self._read_device(d) for d in self._devices]
        with self._lock:
            self._latest = readings
        for reading in readings:
            log.info("%s -> %s %s", reading.device_id, reading.status.value, reading.percent)
            if self._on_alert and self._alerts.should_alert(reading):
                self._safe_call(self._on_alert, reading)
        if self._on_update:
            self._safe_call(self._on_update, readings)
        return readings

    @staticmethod
    def _safe_call(fn: Callable, arg) -> None:
        try:
            fn(arg)
        except Exception:  # noqa: BLE001
            log.exception("callback levantou exceção")

    def _on_push(self, reading: Reading) -> None:
        """Aviso espontâneo de um aparelho: atualiza só ele e repassa se mudou."""
        with self._lock:
            old = {r.device_id: r for r in self._latest}.get(reading.device_id)
            if old is not None and (old.status, old.percent, old.charging) == (
                reading.status, reading.percent, reading.charging,
            ):
                return
            merged = [reading if r.device_id == reading.device_id else r for r in self._latest]
            if old is None:
                merged.append(reading)
            self._latest = merged
            snapshot = list(merged)
        log.info("%s (aviso) -> %s %s carregando=%s", reading.device_id,
                 reading.status.value, reading.percent, reading.charging)
        if self._on_alert and self._alerts.should_alert(reading):
            self._safe_call(self._on_alert, reading)
        if self._on_update:
            self._safe_call(self._on_update, snapshot)

    def _watch(self, device: BatteryDevice) -> None:
        try:
            device.watch(self._stop, self._on_push)
        except Exception:  # noqa: BLE001
            log.exception("escuta de %s terminou", device.device_id)

    def _paused(self) -> bool:
        if self._pause_when is None:
            return False
        try:
            return bool(self._pause_when())
        except Exception:  # noqa: BLE001 - na dúvida, não pausa
            log.exception("checagem de pausa falhou")
            return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            forced, self._forced = self._forced, False
            if forced or not self._paused():
                self.poll_once()
                wait_s = self._interval_s
            else:
                wait_s = self._pause_retry_s  # jogando: não toca nos aparelhos, tenta de novo logo
            self._wake.wait(wait_s)
            self._wake.clear()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="monitor-bateria", daemon=True)
        self._thread.start()
        self._watchers = []
        for device in self._devices:
            if getattr(device, "supports_push", False):
                t = threading.Thread(target=self._watch, args=(device,),
                                     name=f"escuta-{device.device_id}", daemon=True)
                t.start()
                self._watchers.append(t)

    def refresh_now(self) -> None:
        self._forced = True  # pedido do usuário vale mesmo durante o jogo
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
        for t in self._watchers:
            t.join(timeout=3)

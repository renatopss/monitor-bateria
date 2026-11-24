import threading
import time

import pytest

from fakes import FakeFactory, FakeTransport
from monitor_bateria.devices.base import BatteryDevice
from monitor_bateria.models import Reading, Status
from monitor_bateria.service import AlertTracker, MonitorService
from monitor_bateria.transport import HidTarget


class Dummy(BatteryDevice):
    device_id, name = "dummy", "Dummy"
    target = HidTarget(1, 2, 3)

    def __init__(self, behaviour, ident="dummy"):
        super().__init__(FakeFactory(FakeTransport()))
        self.behaviour = behaviour
        self.device_id = ident  # instância própria
        self.calls = 0

    def _read_percent(self, transport):  # pragma: no cover
        raise NotImplementedError

    def read(self):
        self.calls += 1
        return self.behaviour(self)


def ok(p, ident="dummy"):
    return lambda self: Reading(ident, "Dummy", Status.OK, p)


def test_one_bad_plugin_does_not_break_the_others():
    def boom(self): raise RuntimeError("quebrou")
    def hang(self): time.sleep(5)
    good = Dummy(ok(66, "good"), "good")
    svc = MonitorService([Dummy(boom, "boom"), Dummy(hang, "hang"), good], 60, 20, device_timeout_s=0.2)
    by_id = {r.device_id: r for r in svc.poll_once()}
    assert by_id["good"].percent == 66
    assert by_id["boom"].status is Status.ERROR
    assert by_id["hang"].status is Status.TIMEOUT


def test_plugin_returning_garbage_is_contained():
    svc = MonitorService([Dummy(lambda self: "lixo", "g")], 60, 20, device_timeout_s=1)
    assert svc.poll_once()[0].status is Status.ERROR


def test_plugin_cannot_impersonate_another_device():
    svc = MonitorService([Dummy(ok(99, "outro"), "eu")], 60, 20, device_timeout_s=1)
    assert svc.poll_once()[0].status is Status.ERROR


def test_callback_exceptions_do_not_stop_polling():
    def bad_cb(_): raise RuntimeError("x")
    svc = MonitorService([Dummy(ok(10))], 60, 20, on_update=bad_cb, on_alert=bad_cb)
    assert svc.poll_once()[0].percent == 10


def test_alert_fires_once_and_rearms_after_recovery():
    t = AlertTracker(20)
    mk = lambda p: Reading("d", "D", Status.OK, p)
    assert t.should_alert(mk(25)) is False
    assert t.should_alert(mk(20)) is True
    assert t.should_alert(mk(15)) is False          # já avisou
    assert t.should_alert(mk(25)) is False          # ainda dentro da histerese
    assert t.should_alert(mk(30)) is False          # recuperou: rearma
    assert t.should_alert(mk(19)) is True


def test_alert_ignores_unreadable_states():
    t = AlertTracker(20)
    assert t.should_alert(Reading("d", "D", Status.ERROR)) is False


def test_background_loop_polls_then_stops_quickly():
    dev = Dummy(ok(50))
    svc = MonitorService([dev], interval_s=3600, low_percent=20)
    svc.start()
    deadline = time.monotonic() + 2
    while dev.calls < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert dev.calls == 1                   # leu uma vez e dorme (sem laço ocupado)
    time.sleep(0.2)
    assert dev.calls == 1
    svc.refresh_now()
    deadline = time.monotonic() + 2
    while dev.calls < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert dev.calls == 2
    t0 = time.monotonic()
    svc.stop()
    assert time.monotonic() - t0 < 2
    assert threading.active_count() >= 1


def test_polling_is_paused_while_gaming_and_resumes_after():
    import threading, time
    from monitor_bateria.service import MonitorService
    from monitor_bateria.models import Reading, Status

    class Dev:
        device_id, name = "d", "D"
        reads = 0
        def read(self):
            Dev.reads += 1
            return Reading("d", "D", Status.OK, 50)

    gaming = {"on": True}
    svc = MonitorService([Dev()], interval_s=0.05, low_percent=20,
                         pause_when=lambda: gaming["on"], pause_retry_s=0.05)
    svc.start()
    time.sleep(0.4)
    assert Dev.reads == 0                      # jogando: nenhum acesso ao aparelho
    gaming["on"] = False
    time.sleep(0.4)
    assert Dev.reads >= 1                      # saiu do jogo: voltou a ler
    svc.stop()


def test_manual_refresh_works_even_while_gaming():
    import time
    from monitor_bateria.service import MonitorService
    from monitor_bateria.models import Reading, Status

    class Dev:
        device_id, name = "d", "D"
        reads = 0
        def read(self):
            Dev.reads += 1
            return Reading("d", "D", Status.OK, 50)

    svc = MonitorService([Dev()], interval_s=60, low_percent=20, pause_when=lambda: True, pause_retry_s=60)
    svc.start()
    time.sleep(0.2)
    assert Dev.reads == 0
    svc.refresh_now()
    time.sleep(0.4)
    assert Dev.reads == 1
    svc.stop()


def test_pause_check_failure_does_not_pause():
    from monitor_bateria.service import MonitorService
    def boom():
        raise RuntimeError("x")
    svc = MonitorService([], interval_s=60, low_percent=20, pause_when=boom)
    assert svc._paused() is False


# ---- avisos espontâneos (push) --------------------------------------------
def test_push_updates_only_that_device_and_dedupes():
    from monitor_bateria.models import Reading, Status
    from monitor_bateria.service import MonitorService
    calls = []
    svc = MonitorService([], 1800, 20, on_update=calls.append)
    svc._latest = [Reading("a", "A", Status.OK, 50), Reading("b", "B", Status.OK, 70, charging=False)]
    svc._on_push(Reading("b", "B", Status.OK, 70, charging=True))
    svc._on_push(Reading("b", "B", Status.OK, 70, charging=True))  # repetido: ignora
    assert len(calls) == 1
    assert [(r.device_id, r.percent, r.charging) for r in calls[0]] == [("a", 50, None), ("b", 70, True)]
    assert svc.latest == calls[0]


def test_charging_reading_does_not_fire_low_alert():
    from monitor_bateria.models import Reading, Status
    from monitor_bateria.service import AlertTracker
    t = AlertTracker(20)
    assert not t.should_alert(Reading("a", "A", Status.OK, 10, charging=True))

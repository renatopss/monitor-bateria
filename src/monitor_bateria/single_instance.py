"""Garante uma única cópia rodando (mutex nomeado do Windows)."""
from __future__ import annotations

import sys

_handle = None  # mantém o mutex vivo enquanto o processo existir


def acquire_single_instance(name: str = "Local\\monitor-bateria-7c1f") -> bool:
    global _handle
    if sys.platform != "win32":
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.CreateMutexW(None, False, name)
    already_exists = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    if already_exists:
        return False
    _handle = handle
    return True


def enable_dpi_awareness() -> None:
    """Sem isso o Windows estica o ícone de 16 px em telas com escala (fica pequeno e borrado)."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]  # por monitor
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def tray_icon_size(default: int = 32) -> int:
    """Tamanho real, em pixels, do ícone pequeno da bandeja (SM_CXSMICON)."""
    if sys.platform != "win32":
        return default
    import ctypes

    try:
        size = int(ctypes.windll.user32.GetSystemMetrics(49))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return default
    return size if 16 <= size <= 64 else default


def work_area() -> tuple[int, int, int, int] | None:
    """Área útil da tela (sem a barra de tarefas): (esquerda, topo, direita, base)."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom) if ok else None


def fullscreen_app_active() -> bool:
    """True se um jogo/app em tela cheia (ou apresentação) está em primeiro plano.

    Usado para esconder o widget e pausar as leituras enquanto você joga. É barato (2 chamadas
    do Windows) e nunca levanta exceção: na dúvida devolve False.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32  # type: ignore[attr-defined]

        # 1) a resposta oficial do Windows: ocupado / Direct3D em tela cheia / apresentação.
        state = ctypes.c_int(0)
        if shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0 and state.value in (2, 3, 4):
            return True

        # 2) reserva: a janela em primeiro plano cobre o monitor inteiro (jogos em janela sem borda).
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, name, 64)
        if name.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return False  # área de trabalho e barra de tarefas não contam

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        rect = wintypes.RECT()
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        m = info.rcMonitor
        return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    except Exception:  # noqa: BLE001 - nunca atrapalhar o app por causa dessa checagem
        return False


def lower_priority() -> None:
    """Prioridade abaixo do normal: o app nunca disputa CPU com jogos ou outros programas."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:  # noqa: BLE001
        pass

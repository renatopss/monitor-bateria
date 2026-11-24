"""Regras de desenvolvimento seguro, verificadas no código-fonte (AST)."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "monitor_bateria"
FILES = sorted(SRC.rglob("*.py"))

BANNED_IMPORTS = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "ftplib",
    "smtplib", "telnetlib", "xmlrpc", "subprocess", "pickle", "marshal", "shelve", "importlib",
    "runpy", "webbrowser", "winreg",
}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "system", "popen", "startfile"}
ONLY_IN = {"hid": "transport.py", "pystray": "tray.py", "ctypes": "single_instance.py",
           "tkinter": {"ui_colors.py", "ui_widget.py"}}


def imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_network_shell_or_dynamic_code(path):
    tree = parse(path)
    assert not (set(imports(tree)) & BANNED_IMPORTS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            assert name not in BANNED_CALLS, f"{path.name}: chamada proibida {name}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_sensitive_libraries_stay_in_their_module(path):
    used = set(imports(parse(path)))
    for lib, owner in ONLY_IN.items():
        if lib in used:
            owners = owner if isinstance(owner, set) else {owner}
            assert path.name in owners, f"{lib} só pode ser importado em {sorted(owners)}"


def test_plugins_cannot_import_hid_or_sockets_directly():
    for path in (SRC / "devices").glob("*.py"):
        assert not ({"hid", "ctypes", "pystray", "tkinter"} & set(imports(parse(path))))


def test_requirements_pin_exact_versions_with_hashes():
    req = (SRC.parent.parent / "requirements.txt").read_text()
    lines = [l for l in req.splitlines() if l.strip() and not l.startswith(("#", " ", "\t", "--"))]
    assert lines and all("==" in l for l in lines)
    assert "--hash=sha256:" in req


def test_no_banned_libs_in_requirements():
    req = (SRC.parent.parent / "requirements.txt").read_text().lower()
    assert not any(bad in req for bad in ("requests", "httpx", "urllib3", "aiohttp"))


def test_dpi_and_icon_size_helpers_are_safe_off_windows(monkeypatch):
    from monitor_bateria.single_instance import enable_dpi_awareness, tray_icon_size
    assert enable_dpi_awareness() is None
    monkeypatch.setattr("sys.platform", "linux")
    assert tray_icon_size() == 32 and tray_icon_size(24) == 24


def test_fullscreen_check_is_false_off_windows():
    from monitor_bateria.single_instance import fullscreen_app_active
    assert fullscreen_app_active() is False
    from monitor_bateria.single_instance import lower_priority
    assert lower_priority() is None

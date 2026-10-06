"""Janela propria do app: partes que nao dependem de ter uma tela (limites, sinal, enderecos permitidos, inicio com o Windows)."""
from pathlib import Path

import pytest

from src.jefrey.native import autostart, control, shell


def test_external_only_google_https():
    assert shell.is_external("https://accounts.google.com/o/oauth2/v2/auth?x=1")
    assert shell.is_external("https://console.cloud.google.com/apis/credentials")
    assert not shell.is_external("http://accounts.google.com/")  # sem https
    assert not shell.is_external("https://accounts.google.com.evil.com/")
    assert not shell.is_external("file:///C:/Windows/System32/cmd.exe")
    assert not shell.is_external("javascript:alert(1)")
    assert not shell.is_external("")


def test_open_external_refuses_other_hosts(monkeypatch):
    opened = []
    monkeypatch.setattr(shell.webbrowser, "open", lambda u: opened.append(u) or True)
    assert shell.open_external("https://accounts.google.com/x")
    assert not shell.open_external("https://example.com/")
    assert opened == ["https://accounts.google.com/x"]


def test_clamp_state_keeps_window_reachable():
    ok = shell.clamp_state({"w": 1000, "h": 700, "x": 100, "y": 80}, (1920, 1080))
    assert ok == {"w": 1000, "h": 700, "x": 100, "y": 80, "fullscreen": True}
    off = shell.clamp_state({"w": 5000, "h": 10, "x": 4000, "y": -500}, (1920, 1080))  # monitor que sumiu
    assert "x" not in off and "y" not in off
    assert off["w"] == 1920 and off["h"] == shell.MIN_SIZE[1]
    assert shell.clamp_state({}, (1920, 1080))["w"] == shell.MAIN_SIZE[0]


def test_state_roundtrip_and_garbage(tmp_path: Path):
    shell.save_state(tmp_path, {"w": 900, "h": 600, "x": 5, "y": 6, "lixo": "x"})
    assert shell.load_state(tmp_path) == {"w": 900, "h": 600, "x": 5, "y": 6}
    (tmp_path / "config" / shell.STATE_FILE).write_text("nao e json", encoding="utf-8")
    assert shell.load_state(tmp_path) == {}


def test_second_launch_leaves_signal(tmp_path: Path):
    shell.ask_running_to_show(tmp_path)
    assert shell.signal_path(tmp_path).is_file()


def test_window_hooks_and_quit():
    control.set_window_hooks(None, None)
    assert not control.has_window() and not control.show_window() and not control.show_orb()
    calls = []
    control.set_window_hooks(lambda: calls.append("show"), lambda: calls.append("orb"))
    try:
        assert control.has_window() and control.show_window() and control.show_orb()
        assert calls == ["show", "orb"]
    finally:
        control.set_window_hooks(None, None)


def test_autostart_only_in_installed_program(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    assert autostart.command() is None and not autostart.available()
    assert autostart.set_enabled(True) is False  # em desenvolvimento nao registra nada
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\Program Files\Jefrey\Jefrey.exe")
    cmd = autostart.command()
    assert cmd and cmd.endswith("--minimized") and cmd.startswith('"')


def test_browser_fallback_switch(monkeypatch):
    monkeypatch.setenv("JEFREY_WINDOW", "browser")
    assert shell.webview_available() is False


def test_orb_is_a_spa_page():
    from src.jefrey.api.auth_middleware import _SPA_PAGES

    assert "/orb" in _SPA_PAGES


@pytest.mark.parametrize("path", ["/system/open-external", "/system/autostart", "/system/orb", "/system/show", "/system/shell"])
def test_system_routes_need_login(path):
    from fastapi.testclient import TestClient

    from src.jefrey.api.main import app

    c = TestClient(app, base_url="http://127.0.0.1:8000")
    r = c.post(path, json={"url": "https://accounts.google.com/", "enabled": True}) if path != "/system/autostart" else c.put(path, json={"enabled": True})
    assert r.status_code in (401, 403, 405)


def test_build_bundles_the_window_engine():
    bat = (Path(__file__).resolve().parents[1] / "packaging" / "build_exe.bat").read_text(encoding="utf-8")
    for flag in ("--collect-all webview", "--collect-all pythonnet", "--collect-all clr_loader", "webview.platforms.edgechromium"):
        assert flag in bat
    assert "pywebview" in (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")


def test_fullscreen_is_default_and_remembered(tmp_path: Path):
    assert shell.clamp_state({}, (1920, 1080))["fullscreen"] is True
    assert shell.clamp_state({"fullscreen": False}, (1920, 1080))["fullscreen"] is False
    shell.save_state(tmp_path, {"fullscreen": False, "w": 900})
    assert shell.load_state(tmp_path) == {"w": 900, "fullscreen": False}

import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import sysinfo as S


def test_memoria_em_porcentagem_valida():
    used, total = S.memory()
    assert 0 <= used <= 100 and total >= 0


def test_cpu_na_primeira_chamada_nao_inventa_e_depois_fica_entre_0_e_100():
    S._last_cpu = None
    assert S.cpu_percent() is None  # sem referencia anterior, nao ha como medir
    import sys, time
    time.sleep(0.2)
    v = S.cpu_percent()
    assert (v is None) if sys.platform != "win32" else (v is None or 0 <= v <= 100)


def test_fora_do_windows_cpu_e_none(monkeypatch):
    monkeypatch.setattr(S.sys, "platform", "linux")
    assert S.cpu_percent() is None


def test_api_telemetria_exige_login_e_nao_gasta_o_limite(monkeypatch):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    assert c.get("/system/telemetry").status_code == 401
    tok = c.post("/auth/dev-token", json={"user_id": "tele"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    d = c.get("/system/telemetry", headers=h).json()
    assert {"ram_pct", "ram_total_gb", "cpu_pct", "uptime_s", "brain", "reserves"} <= set(d)
    assert all(c.get("/system/telemetry", headers=h).status_code == 200 for _ in range(80))

"""Maquina de cliente: sem .env nem variaveis do Jefrey, so com o que o lancador define, tudo precisa subir.

So roda quando NAO existe .env no projeto (nunca mexemos nos segredos de quem desenvolve); no CI roda sempre.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif((ROOT / ".env").exists(), reason="existe .env local: o teste de maquina limpa roda no CI")

CODE = """
import os, sys
sys.path.insert(0, {root!r})
from pathlib import Path
from src.jefrey.native.launcher import build_env
os.environ.update(build_env(Path({home!r}), base={{}}))
os.chdir({home!r})
from fastapi.testclient import TestClient
from src.jefrey.api.main import app
with TestClient(app, base_url="http://127.0.0.1:8000") as c:
    assert c.get("/health").status_code == 200
    t = c.post("/auth/dev-token", json={{"user_id": "cliente"}})
    assert t.status_code == 200
    H = {{"Authorization": "Bearer " + t.json()["access_token"]}}
    bad = [p for p in ("/skills", "/memory/recent", "/reminders", "/approvals/pending", "/settings/llm")
           if c.get(p, headers=H).status_code != 200]
    st = c.get("/api/status").json()
    assert st["postgres"]["status"] == "ok" and st["redis"]["status"] == "off", st
    print("RESULT", bad)
"""


def test_modo_nativo_sobe_numa_maquina_limpa():
    env = {k: v for k, v in os.environ.items() if not k.startswith("JEFREY_")}
    home = tempfile.mkdtemp()
    r = subprocess.run([sys.executable, "-c", CODE.format(root=str(ROOT), home=home)], cwd=tempfile.mkdtemp(),
                       env=env, capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr[-1200:]
    assert "RESULT []" in r.stdout, r.stdout[-600:]

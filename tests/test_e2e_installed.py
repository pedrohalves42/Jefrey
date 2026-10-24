"""A bateria do instalado: o resumo separa falha (obrigatoria) de lentidao (aviso)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("e2e_installed", Path(__file__).resolve().parents[1] / "scripts" / "e2e_installed.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def test_tudo_ok_e_lento_so_avisa():
    r = E.summarize([{"name": "a", "ok": True, "seconds": 1.0}, {"name": "b", "ok": True, "seconds": 20.0}])
    assert r == {"ok": True, "failed": [], "slow": ["b"]}


def test_falha_derruba():
    r = E.summarize([{"name": "a", "ok": False, "seconds": 1.0}, {"name": "b", "ok": True, "seconds": 2.0}])
    assert r["ok"] is False and r["failed"] == ["a"]

"""Tarefa 4 do plano: o relatorio da avaliacao diz qual cerebro e qual funcao acertam mais e quanto demoram."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("run_evals_rel", ROOT / "evals/run_evals.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_evals_rel"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_relatorio_traz_cerebros_medidas_e_resultado_por_pedido():
    E = _load()
    results = [E.Result("hora", "leigos", True, "ok", 1.2), E.Result("noticia", "leigos", False, "sem fonte", 14.0)]
    brains = [{"id": "groq", "role": "principal", "model": "gpt-oss"}, {"id": "gemini", "role": "reserva", "model": "flash"}]
    metrics = {"rapido": {"groq": {"n": 8, "ok": 8, "median": 0.5}}}
    rel = E.build_report("http://x", results, brains, metrics)
    assert rel["rate"] == 0.5
    assert rel["brains"][0]["id"] == "groq"
    assert rel["metrics"]["rapido"]["groq"]["n"] == 8
    assert [r["name"] for r in rel["results"]] == ["hora", "noticia"]
    assert rel["results"][1]["ok"] is False and rel["results"][1]["seconds"] == 14.0


def test_resumo_por_funcao_aponta_o_cerebro_mais_rapido_e_confiavel():
    E = _load()
    metrics = {
        "conversa": {"gemini": {"n": 10, "ok": 10, "median": 20.0}, "groq": {"n": 10, "ok": 10, "median": 0.5}},
        "rapido": {"groq": {"n": 3, "ok": 3, "median": 0.4}},  # poucos dados: nao conclui
    }
    melhor = E.best_by_role(metrics)
    assert melhor["conversa"] == "groq"
    assert "rapido" not in melhor

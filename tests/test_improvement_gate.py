"""Tarefa 5 do plano: 👎 vira um caso de teste local para a pessoa revisar. O app nunca altera o proprio codigo."""
import asyncio
import json

import pytest
from sqlalchemy import create_engine

from src.jefrey.application.improvement import save_case


def _arquivos(raiz):
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*") if p.is_file())


def test_um_down_gera_um_caso_com_pergunta_resposta_e_esperado_vazio(tmp_path):
    destino = tmp_path / "data" / "feedback_cases"
    arq = save_case(destino, "msg-1", "Qual a capital da Austrália?", "É Sydney.", "errou")
    caso = json.loads(arq.read_text(encoding="utf-8"))
    assert caso["question"] == "Qual a capital da Austrália?" and caso["answer"] == "É Sydney."
    assert caso["expected"] == "" and caso["note"] == "errou" and caso["message_id"] == "msg-1"


def test_nada_fora_da_pasta_de_casos_e_alterado(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "llm.runtime.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src.py").write_text("x = 1", encoding="utf-8")
    antes = _arquivos(tmp_path)
    save_case(tmp_path / "data" / "feedback_cases", "msg-2", "pergunta", "resposta", "")
    novos = [a for a in _arquivos(tmp_path) if a not in antes]
    assert len(novos) == 1 and novos[0].replace("\\", "/").startswith("data/feedback_cases/")
    assert (tmp_path / "src.py").read_text(encoding="utf-8") == "x = 1"


def test_texto_com_segredo_nao_e_guardado(tmp_path):
    destino = tmp_path / "casos"
    assert save_case(destino, "msg-3", "minha chave é sk-proj-" + "a1b2c3d4e5" * 4, "ok", "") is None
    assert not destino.exists() or not list(destino.iterdir())


def test_nome_do_arquivo_nao_aceita_caminho_na_id(tmp_path):
    destino = tmp_path / "casos"
    arq = save_case(destino, "../../fora", "p", "r", "")
    assert arq.parent == destino  # a id vira so um nome seguro, nunca um caminho


@pytest.fixture()
def rotas(tmp_path, monkeypatch):
    from src.jefrey.api import feedback_routes as FR
    from src.jefrey.adapters.outbound.brain_metrics import BrainMetrics
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: create_engine(f"sqlite:///{tmp_path}/r.db"))
    store = BrainMetrics()
    monkeypatch.setattr(FR, "_store", lambda: store)
    monkeypatch.setattr(FR, "_cases_dir", lambda: tmp_path / "data" / "feedback_cases")
    return FR


class _Req:
    state = type("S", (), {"user_id": "pedro"})()


def test_down_com_pergunta_e_resposta_cria_o_caso_e_up_nao(rotas, tmp_path):
    corpo_up = rotas.FeedbackBody(message_id="m1", value="up", question="p", answer="r")
    asyncio.run(rotas.send_feedback(_Req(), corpo_up))
    assert not (tmp_path / "data" / "feedback_cases").exists()
    corpo_down = rotas.FeedbackBody(message_id="m2", value="down", question="p", answer="r", note="errado")
    asyncio.run(rotas.send_feedback(_Req(), corpo_down))
    assert len(list((tmp_path / "data" / "feedback_cases").glob("*.json"))) == 1

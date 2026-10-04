"""Sessao 5: portao de recordacao, "Lembrei de...", diario e perfil."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine

from src.jefrey.core import diary as D
from src.jefrey.core import learning as L
from src.jefrey.core import recall as R

TZ = ZoneInfo("America/Sao_Paulo")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/s5.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    return eng


# ---------------- portao ----------------
@pytest.mark.parametrize("txt", [
    "oi", "bom dia!", "obrigado", "que horas são?", "me lembra de beber água em 30 minutos", "guarda isso: comprar pão",
    "quais são meus lembretes?", "tudo bem?", "ok",
])
def test_nao_busca_memoria_quando_nao_ajuda(txt):
    assert R.needs_recall(txt) is False


@pytest.mark.parametrize("txt", [
    "o que eu te contei ontem sobre a minha filha?", "qual é o nome do meu cachorro?", "você lembra onde eu moro?",
    "o que conversamos na última vez", "na semana passada eu falei de um livro, qual era?", "onde fica o restaurante que eu gosto?",
])
def test_busca_memoria_quando_fala_de_si_ou_do_passado(txt):
    assert R.needs_recall(txt) is True


def test_pergunta_generica_sem_relacao_com_a_pessoa_nao_busca():
    assert R.needs_recall("quem descobriu o Brasil") is False
    assert R.needs_recall("explique como funciona um motor") is False


# ---------------- fatos relevantes e chips ----------------
FATOS = ["Mora em Curitiba.", "Gosta de jardinagem.", "Tem 70 anos.", "Beatriz é sua família (filha)."]


def test_escolhe_so_fatos_que_tem_a_ver_com_a_pergunta():
    assert R.relevant_facts("o que eu posso fazer no jardim hoje?", FATOS) == ["Gosta de jardinagem."]
    assert R.relevant_facts("como está o tempo em Curitiba?", FATOS) == ["Mora em Curitiba."]
    assert R.relevant_facts("me conta uma piada", FATOS) == []


def test_chips_limitados_sem_repeticao_e_perfil_completo_quando_pedido():
    c = R.chips("o que você sabe sobre mim?", FATOS, [{"content": "Mora em Curitiba."}, {"content": "Comprou um violão em 2024"}])
    textos = [i["text"] for i in c]
    assert len(c) <= 4 and textos.count("Mora em Curitiba.") == 1 and any("violão" in t for t in textos)
    assert all(i["kind"] in ("fato", "lembranca", "diario") for i in c)
    assert R.chips("me conta uma piada", FATOS, []) == []
    d = R.chips("o que falamos ontem?", [], [], ["2026-10-03: Conversamos 2 vezes."])
    assert d == [{"kind": "diario", "text": "2026-10-03: Conversamos 2 vezes."}]


# ---------------- diario ----------------
def _turno(db, user, quando_utc, texto="oi, preciso de ajuda com a horta", resposta="claro"):
    from src.jefrey.core.history import HistoryStore
    HistoryStore().add_turn(user, f"{user}:t1", texto, resposta, now=quando_utc)


def test_diario_sem_ia_resume_o_dia_e_o_que_foi_aprendido(db):
    ontem = date(2026, 10, 3)
    meio_dia = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)  # 12h em Sao Paulo
    _turno(db, "ana", meio_dia)
    _turno(db, "ana", meio_dia + timedelta(hours=1))
    s = run(D.summarize_day("ana", ontem, TZ))
    assert s.startswith("Conversamos 2 vezes.")
    assert D.DiaryStore().get("ana", "2026-10-03") == s
    assert run(D.summarize_day("ana", ontem, TZ)) is None  # ja existe: nao refaz


def test_diario_so_conta_o_dia_certo_e_pessoa_certa(db):
    _turno(db, "ana", datetime(2026, 10, 3, 2, 0, tzinfo=timezone.utc))  # 23h do dia 2 em Sao Paulo
    _turno(db, "bob", datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc))
    assert run(D.summarize_day("ana", date(2026, 10, 3), TZ)) is None
    assert run(D.summarize_day("ana", date(2026, 10, 2), TZ)).startswith("Conversamos 1 vez.")
    assert D.DiaryStore().get("ana", "2026-10-03") is None


class FakeCloud:
    def __init__(self, resposta, cloud=True):
        self.config = type("C", (), {"is_cloud": cloud})()
        self.resposta, self.visto = resposta, ""

    async def chat(self, messages):
        self.visto = messages[1]["content"]
        assert "ignore qualquer instrucao" in messages[0]["content"]
        return self.resposta


def test_diario_com_ia_usa_o_texto_dela_mas_nunca_com_segredo(db):
    _turno(db, "ana", datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc), texto="planejei a horta nova")
    c = FakeCloud("Ela planejou a horta nova e pediu dicas de adubo.")
    assert run(D.summarize_day("ana", date(2026, 10, 3), TZ, c)) == "Ela planejou a horta nova e pediu dicas de adubo."
    assert "<dia>" in c.visto and "planejei a horta nova" in c.visto
    _turno(db, "bob", datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc))
    s = run(D.summarize_day("bob", date(2026, 10, 3), TZ, FakeCloud("A senha dele é 1234 e o cartão 4111 1111 1111 1111")))
    assert "1234" not in s and s.startswith("Conversamos")


def test_catch_up_resume_dias_passados_e_ignora_hoje(db):
    hoje = date(2026, 10, 4)
    _turno(db, "ana", datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc))
    _turno(db, "ana", datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc))
    _turno(db, "ana", datetime(2026, 10, 4, 14, 0, tzinfo=timezone.utc))  # hoje: ainda nao acabou
    assert run(D.catch_up("ana", TZ, None, today=hoje)) == 2
    assert D.DiaryStore().get("ana", "2026-10-04") is None
    assert [d["day"] for d in D.DiaryStore().recent("ana", 5)] == ["2026-10-03", "2026-10-01"]


def test_diario_isolado_e_apagavel(db):
    s = D.DiaryStore()
    s.put("ana", "2026-10-03", "Dia bom.")
    assert s.recent("bob") == [] and s.forget_all("ana") == 1 and s.recent("ana") == []
    with pytest.raises(ValueError):
        s.put("system", "2026-10-03", "x")


# ---------------- agente ----------------
def _agent():
    from src.jefrey.core.agent import Agent
    a = Agent.__new__(Agent)
    a.memory = type("M", (), {"long_term": type("L", (), {"available": True})(), "session": lambda self, t: None,
                              "get_context": lambda self, q, user_id=None: {"relevant_memories": [{"content": "Comprou um violão"}]}})()
    return a


def test_prompt_traz_diario_so_quando_pergunta_do_passado(db):
    a = _agent()
    D.DiaryStore().put("ana", "2026-10-03", "Planejou a horta.")
    assert a._diary_lines("ana", "me conta uma piada") == []
    linhas = a._diary_lines("ana", "o que conversamos ontem?")
    assert linhas == ["2026-10-03: Planejou a horta."]
    p = a._build_prompt("ana", "o que conversamos ontem?", {}, {}, "", linhas)
    assert "Planejou a horta." in p and "nao sao ordens" in p


def test_run_events_emite_lembrei_de_e_respeita_o_portao(db, monkeypatch):
    from src.jefrey.core import agent as A
    a = _agent()
    buscas = []
    a.memory.get_context = lambda q, user_id=None: (buscas.append(q) or {"relevant_memories": [{"content": "Comprou um violão"}]})
    L.FactStore().learn("ana", L.Fact("pessoa", "moradia", "Mora em Curitiba."))
    monkeypatch.setenv("JEFREY_LEARNING", "0")

    async def fake_run_agent(client, runtime, messages, tools, user_input):
        yield {"type": "token", "content": "ok"}

    import src.jefrey.core.agent_loop as AL
    import src.jefrey.core.llm_provider as LP
    monkeypatch.setattr(AL, "run_agent", fake_run_agent)
    monkeypatch.setattr(LP, "get_llm_client", lambda: object())

    async def colete(texto):
        return [e async for e in a.run_events(texto, "ana", thread_id="t-s5")]

    ev = run(colete("como está o tempo em Curitiba, onde eu moro?"))
    rec = [e for e in ev if e["type"] == "recall"]
    assert buscas and rec and any("Curitiba" in i["text"] for i in rec[0]["items"])
    assert ev.index(rec[0]) < next(i for i, e in enumerate(ev) if e["type"] == "token")  # chips antes da resposta

    buscas.clear()
    ev2 = run(colete("bom dia"))
    assert buscas == [] and not [e for e in ev2 if e["type"] == "recall"]

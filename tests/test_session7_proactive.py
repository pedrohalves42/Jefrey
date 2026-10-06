"""Sessao 7: resumo do dia, avisos do Windows sem incomodar, lembretes e estado "estudando/aprendendo"."""
import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.jefrey.core import activity as ACT
from src.jefrey.core import briefing as B
from src.jefrey.core import learning as L
from src.jefrey.core import notify as N
from src.jefrey.core import studies as S

TZ = ZoneInfo("America/Sao_Paulo")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/s7.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    B._notified.clear()
    N.set_sink(None)
    N._count.clear()
    yield eng
    N.set_sink(None)


def _manha(h=9, m=0):
    return datetime(2026, 10, 4, h, m, tzinfo=TZ)


# ---------------- texto ----------------
@pytest.mark.parametrize("h,esperado", [(5, "Bom dia"), (11, "Bom dia"), (12, "Boa tarde"), (17, "Boa tarde"), (18, "Boa noite"), (23, "Boa noite")])
def test_saudacao_pela_hora(h, esperado):
    assert B.greeting_for(h) == esperado


@pytest.mark.parametrize("fato,hoje,esperado", [
    ("Aniversário: dia 4 de outubro.", date(2026, 10, 4), True), ("Aniversário: dia 4 de outubro.", date(2026, 10, 5), False),
    ("Aniversário: dia 12 de março.", date(2026, 3, 12), True), ("Aniversário: dia 12 de mar.", date(2026, 3, 12), True),
    ("Aniversário: dia 7 de 11.", date(2026, 11, 7), True), ("Gosta de jardinagem.", date(2026, 10, 4), False),
])
def test_aniversario(fato, hoje, esperado):
    assert B.birthday_today([fato], hoje) is esperado


def _r(texto, label):
    return {"text": texto, "due_label": label}


def test_texto_completo_informal_e_curto():
    t = B.build_text(name="Pedro", now=_manha(), today_reminders=[_r("tomar o remédio", "hoje às 20:00"), _r("ligar para a Bia", "hoje às 15:30")],
                     overdue=[_r("pagar a luz", "ontem às 10:00")], studied=[{"title": "Horta em casa", "level_label": "Iniciante"}],
                     birthday=True, yesterday="Conversamos 2 vezes.")
    linhas = t.splitlines()
    assert linhas[0] == "Bom dia, Pedro!" and "aniversário" in linhas[1]
    assert "Ficou pendente: pagar a luz." in t and "tomar o remédio (20:00)" in t and "ligar para a Bia (15:30)" in t
    assert "estudei sobre Horta em casa" in t and "Ontem: Conversamos 2 vezes." in t
    assert "Sir" not in t and "senhor" not in t.lower()


def test_texto_de_dia_vazio_e_sem_nome():
    t = B.build_text(name=None, now=_manha(), today_reminders=[], overdue=[], studied=[])
    assert t.startswith("Bom dia!") and "Dia tranquilo" in t


# ---------------- armazenamento ----------------
def test_preferencias_validas_e_isoladas(db):
    s = B.BriefingStore()
    assert s.get_prefs("ana") == {"enabled": True, "hour": 8, "notify": True}
    assert s.set_prefs("ana", hour=7, notify=False) == {"enabled": True, "hour": 7, "notify": False}
    assert s.get_prefs("bob")["hour"] == 8
    for ruim in (4, 13, 99):
        with pytest.raises(ValueError):
            s.set_prefs("ana", hour=ruim)
    with pytest.raises(ValueError):
        s.set_prefs("system", hour=8)


def test_guarda_marca_como_visto_e_apaga(db):
    s = B.BriefingStore()
    s.put("ana", "2026-10-04", "Bom dia!")
    assert s.get("ana", "2026-10-04") == {"day": "2026-10-04", "text": "Bom dia!", "seen": False}
    assert s.mark_seen("ana", "2026-10-04") is True and s.get("ana", "2026-10-04")["seen"] is True
    assert s.get("bob", "2026-10-04") is None and s.mark_seen("bob", "2026-10-04") is False
    assert s.forget_all("ana") == 1 and s.get("ana", "2026-10-04") is None


# ---------------- geracao ----------------
def test_resumo_usa_lembretes_estudos_e_nome(db):
    from src.jefrey.core.profile import ProfileStore
    from src.jefrey.core.reminders import ReminderStore
    ProfileStore().set_name("ana", "Ana")
    rs = ReminderStore()
    rs.add("ana", "tomar o remédio", _manha(20))
    rs.add("ana", "buscar a encomenda", _manha(7))  # ja passou: pendente
    rs.add("ana", "consulta", _manha(9) + timedelta(days=1))  # amanha: fora
    rs.add("bob", "lembrete do bob", _manha(20))
    st = S.StudyStore()
    t = st.add_topic("ana", "horta em casa")
    st.add_guide("ana", t["id"], "Horta em casa", "Comece pequeno.", "corpo", [], 1)
    texto = B.generate("ana", _manha())
    assert texto.startswith("Bom dia, Ana!") and "tomar o remédio" in texto and "Ficou pendente: buscar a encomenda" in texto
    assert "consulta" not in texto and "bob" not in texto.lower() and "estudei sobre Horta em casa" in texto
    assert B.BriefingStore().get("ana", "2026-10-04")["text"] == texto


def test_resumo_so_depois_da_hora_uma_vez_por_dia_e_so_se_ligado(db):
    from src.jefrey.core.profile import ProfileStore
    ProfileStore().set_name("ana", "Ana")
    ProfileStore().set_name("bob", "Bob")
    s = B.BriefingStore()
    s.set_prefs("bob", enabled=False)
    assert run(B.briefing_tick(now=_manha(6, 30), store=s)) == []  # cedo demais
    assert run(B.briefing_tick(now=_manha(8, 5), store=s)) == ["ana"]  # bob desligou
    assert run(B.briefing_tick(now=_manha(9, 0), store=s)) == []  # ja fez hoje
    assert run(B.briefing_tick(now=_manha(8, 5) + timedelta(days=1), store=s)) == ["ana"]  # amanha de novo


# ---------------- avisos do Windows ----------------
def test_sem_destino_nao_mostra_nada():
    assert N.notify("ana", "t", "x", now=_manha()) is False


def test_avisos_respeitam_silencio_e_limite_do_dia():
    vistos = []
    N.set_sink(lambda t, x: vistos.append((t, x)))
    N._count.clear()
    assert N.notify("ana", "Oi", "bom dia", now=_manha(23)) is False  # de madrugada
    assert N.notify("ana", "Oi", "bom dia", now=_manha(6)) is False
    for i in range(N.MAX_PER_DAY):
        assert N.notify("ana", "Oi", f"aviso {i}", now=_manha(10)) is True
    assert N.notify("ana", "Oi", "um a mais", now=_manha(11)) is False  # limite do dia
    assert N.notify("bob", "Oi", "outro usuario", now=_manha(11)) is True  # limite e por pessoa
    assert N.notify("ana", "Lembrete", "remédio", urgent=True, now=_manha(23)) is True  # lembrete sempre chega
    assert len(vistos) == N.MAX_PER_DAY + 2
    assert N.notify("ana", "Oi", "amanhã", now=_manha(10) + timedelta(days=1)) is True  # novo dia, limite zera
    N.set_sink(None)


def test_destino_quebrado_nao_derruba():
    def quebra(t, x):
        raise RuntimeError("sem bandeja")
    N.set_sink(quebra)
    assert N.notify("ana", "t", "x", now=_manha(10)) is False
    N.set_sink(None)


def test_aviso_de_lembrete_chega_uma_vez_so_e_so_quando_vence(db):
    from src.jefrey.core.reminders import ReminderStore
    vistos = []
    N.set_sink(lambda t, x: vistos.append((t, x)))
    rs = ReminderStore()
    rs.add("ana", "tomar o remédio", _manha(9, 0))
    rs.add("ana", "ainda nao e hora", _manha(23, 0))
    assert len(run(B.reminder_tick(now=_manha(9, 5)))) == 1
    assert run(B.reminder_tick(now=_manha(9, 6))) == []  # nao repete
    assert vistos == [("Lembrete", "tomar o remédio")]
    N.set_sink(None)


def test_lembrete_de_madrugada_ainda_avisa(db):
    from src.jefrey.core.reminders import ReminderStore
    vistos = []
    N.set_sink(lambda t, x: vistos.append(x))
    ReminderStore().add("ana", "remédio da madrugada", _manha(3, 0))
    assert len(run(B.reminder_tick(now=_manha(3, 1)))) == 1 and vistos == ["remédio da madrugada"]
    N.set_sink(None)


# ---------------- o que o Jefrey esta fazendo ----------------
def test_estado_de_atividade_com_contagem_e_isolamento():
    assert ACT.current("ana") == {"studying": False, "learning": False, "topic": None}
    with ACT.busy("ana", "estudando", "horta"):
        with ACT.busy("ana", "estudando", "horta"):
            assert ACT.current("ana")["studying"] is True and ACT.current("ana")["topic"] == "horta"
        assert ACT.current("ana")["studying"] is True  # ainda tem uma tarefa
        assert ACT.current("bob")["studying"] is False
    assert ACT.current("ana") == {"studying": False, "learning": False, "topic": None}
    with ACT.busy("ana", "inventado"):
        assert ACT.current("ana")["studying"] is False


def test_aprender_e_estudar_marcam_o_estado_enquanto_rodam(db):
    visto = {}

    class Cloud:
        config = type("C", (), {"is_cloud": True})()

        async def chat(self, messages):
            visto["aprendendo"] = ACT.current("ana")["learning"]
            return "[]"
    run(L.learn_from_turn("ana", "eu estou escrevendo um livro de receitas", "ok", Cloud()))
    assert visto["aprendendo"] is True and ACT.current("ana")["learning"] is False

    st = S.StudyStore()
    t = st.add_topic("ana", "horta em casa")

    class Estudo:
        config = type("C", (), {"is_cloud": True})()

        async def chat(self, messages):
            visto["estudando"] = ACT.current("ana")
            raise RuntimeError("falha")
    with pytest.raises(S.StudyError):
        run(S.study_topic("ana", t["id"], Estudo(), tz=TZ, store=st))
    assert visto["estudando"]["studying"] is True and visto["estudando"]["topic"] == "horta em casa"
    assert ACT.current("ana")["studying"] is False  # liberou mesmo com erro


# ---------------- API ----------------
@pytest.fixture()
def client(db):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apibrief"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def test_api_resumo_do_dia(client):
    c, h = client
    assert c.get("/briefing").status_code == 401 and c.get("/system/activity").status_code == 401
    r = c.get("/briefing", headers=h).json()
    assert r["briefing"] is None and r["prefs"] == {"enabled": True, "hour": 8, "notify": True}
    b = c.post("/briefing/now", headers=h).json()["briefing"]
    assert b["text"].startswith(("Bom dia", "Boa tarde", "Boa noite")) and b["seen"] is False
    assert c.post("/briefing/seen", headers=h).json() == {"ok": True}
    assert c.get("/briefing", headers=h).json()["briefing"]["seen"] is True
    assert c.put("/briefing/prefs", headers=h, json={"hour": 7, "notify": False}).json() == {"enabled": True, "hour": 7, "notify": False}
    assert c.put("/briefing/prefs", headers=h, json={"hour": 20}).status_code == 422
    assert c.get("/system/activity", headers=h).json() == {"studying": False, "learning": False, "topic": None}


def test_lembrete_esquecido_ganha_um_toque_gentil_uma_vez(db):
    from src.jefrey.core.reminders import ReminderStore
    vistos = []
    N.set_sink(lambda t, x: vistos.append((t, x)))
    B._nudged.clear()
    ReminderStore().add("ana", "meditar", _manha(8, 0))
    run(B.reminder_tick(now=_manha(8, 5)))  # avisou
    run(B.reminder_tick(now=_manha(8, 40)))  # ainda nao passou uma hora
    assert [t for t, _ in vistos] == ["Lembrete"]
    run(B.reminder_tick(now=_manha(9, 10)))  # uma hora depois, sem ciente
    run(B.reminder_tick(now=_manha(9, 20)))  # nao repete
    assert [t for t, _ in vistos] == ["Lembrete", "Passou do horário"]
    N.set_sink(None)

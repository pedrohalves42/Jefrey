"""Lembretes: interpretacao de horario em portugues, armazenamento isolado, entrega e rotas."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.jefrey.core import reminders as R
from src.jefrey.core.agent_loop import route_intent, select_tools

TZ = R.local_tz()
# domingo, 4 de outubro de 2026, 10:00 (horario local)
NOW = datetime(2026, 10, 4, 10, 0, tzinfo=TZ)


def when(text, now=NOW):
    return R.parse_when(text, now)


def at(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=TZ)


# ---------------- horario ----------------
@pytest.mark.parametrize("txt,esperado", [
    ("amanha as 8h", at(2026, 10, 5, 8)),
    ("amanhã às 8", at(2026, 10, 5, 8)),
    ("amanha as 8h30", at(2026, 10, 5, 8, 30)),
    ("amanha as 14:45", at(2026, 10, 5, 14, 45)),
    ("hoje as 15h", at(2026, 10, 4, 15)),
    ("depois de amanha as 9", at(2026, 10, 6, 9)),
    ("as 8 da noite", at(2026, 10, 4, 20)),      # 20h hoje ainda e futuro
    ("as 9 da manha", at(2026, 10, 5, 9)),       # 9h de hoje ja passou: amanha
    ("as 22h", at(2026, 10, 4, 22)),
    ("amanha de manha", at(2026, 10, 5, 8)),
    ("amanha de tarde", at(2026, 10, 5, 15)),
    ("amanha a noite", at(2026, 10, 5, 20)),
    ("meio dia", at(2026, 10, 5, 12)),           # meio-dia de hoje ja passou (10h < 12h? nao: 12h e futuro)
    ("sexta as 9", at(2026, 10, 9, 9)),
    ("na segunda as 7h", at(2026, 10, 5, 7)),
    ("domingo as 9", at(2026, 10, 11, 9)),       # hoje e domingo e 9h ja passou: proximo domingo
    ("daqui a 20 minutos", at(2026, 10, 4, 10, 20)),
    ("em 2 horas", at(2026, 10, 4, 12)),
    ("daqui a meia hora", at(2026, 10, 4, 10, 30)),
    ("em 3 dias", at(2026, 10, 7, 10)),
    ("daqui a uma hora", at(2026, 10, 4, 11)),
])
def test_horarios_em_portugues(txt, esperado):
    if txt == "meio dia":
        esperado = at(2026, 10, 4, 12)  # 12h de hoje ainda nao chegou (agora = 10h)
    w = when(txt)
    assert w.due == esperado, (txt, w.due)


def test_amanha_sem_horario_assume_9h_e_avisa():
    w = when("amanha")
    assert w.due == at(2026, 10, 5, 9) and w.assumed_time


def test_repeticao_diaria_e_semanal():
    w = when("todo dia as 8 da manha")
    assert w.repeat == "daily" and w.due == at(2026, 10, 5, 8)
    w = when("todos os dias as 20h")
    assert w.repeat == "daily" and w.due == at(2026, 10, 4, 20)
    w = when("toda sexta as 9")
    assert w.repeat == "weekly" and w.due == at(2026, 10, 9, 9)


@pytest.mark.parametrize("txt", ["", "tomar remedio", "as 25h", "as 8:75", "em 0 minutos", "qualquer hora"])
def test_nao_entendi_quando(txt):
    assert when(txt).due is None


def test_virada_de_mes_e_ano():
    n = at(2026, 12, 31, 23, 30)
    assert when("amanha as 8", n).due == at(2027, 1, 1, 8)
    assert when("daqui a 1 hora", n).due == at(2027, 1, 1, 0, 30)


# ---------------- pedido completo ----------------
@pytest.mark.parametrize("msg,texto", [
    ("me lembra de tomar o remedio amanha as 8h", "tomar o remedio"),
    ("Me lembra de ligar para o dentista amanhã de manhã", "ligar para o dentista"),
    ("me lembre que a reuniao e importante daqui a 2 horas", "a reuniao e importante"),
    ("lembre-me de pagar a conta sexta as 10", "pagar a conta"),
    ("me avisa de buscar o Joao as 18h", "buscar o Joao"),
    ("cria um lembrete de comprar leite hoje as 17h", "comprar leite"),
    ("por favor me lembra de beber agua todo dia as 9h", "beber agua"),
    ("me lembra de tomar o remedio todo dia as 8 da manha", "tomar o remedio"),
])
def test_extrai_o_texto_do_lembrete(msg, texto):
    rq = R.parse_request(msg, NOW)
    assert rq is not None and rq.text == texto, rq
    assert rq.when.due is not None


def test_pedido_sem_horario_pede_o_horario():
    rq = R.parse_request("me lembra de tomar o remedio", NOW)
    assert rq is not None and rq.text == "tomar o remedio" and rq.when.due is None


@pytest.mark.parametrize("msg", ["que horas sao", "voce lembra do meu nome", "o que eu anotei", "anota ai comprar pao", "oi", "me lembra"])
def test_conversa_comum_nao_vira_lembrete(msg):
    assert R.parse_request(msg, NOW) is None


def test_preserva_acentos_e_maiusculas_do_texto():
    rq = R.parse_request("Me lembra de ligar pro João às 8h amanhã", NOW)
    assert rq is not None and rq.text == "ligar pro João"


# ---------------- roteador do agente ----------------
def test_roteador_cria_lembrete_sem_usar_o_modelo():
    name, args = route_intent("Me lembra de tomar o remedio todo dia as 8 da manha")
    assert name == "set_reminder" and args["text"] == "tomar o remedio" and "todo dia" in args["when"]


def test_roteador_lista_lembretes():
    for m in ("quais sao meus lembretes", "meus lembretes", "mostre os lembretes", "tenho lembretes?"):
        assert route_intent(m) == ("list_reminders", {}), m


def test_selecao_oferece_ferramentas_de_lembrete():
    avail = ["set_reminder", "list_reminders", "cancel_reminder", "save_note"]
    assert "set_reminder" in select_tools("preciso de um lembrete para amanha", avail)
    assert "set_reminder" not in select_tools("anota que comprei pao", avail)


# ---------------- armazenamento ----------------
@pytest.fixture()
def store(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/r.db")
    import src.jefrey.core.db as db
    monkeypatch.setattr(db, "get_engine", lambda: eng)
    orig = R.describe_due
    monkeypatch.setattr(R, "describe_due", lambda due, now=None: orig(due, now or NOW))  # "hoje" = NOW do teste, nao o relogio real
    return R.ReminderStore()


def test_criar_listar_e_isolar_por_usuario(store):
    r = store.add("ana", "tomar remedio", NOW + timedelta(hours=1))
    store.add("bob", "segredo do bob", NOW + timedelta(hours=1))
    assert [x["text"] for x in store.pending("ana")] == ["tomar remedio"]
    assert r["due_label"].startswith("hoje às 11:00")
    assert store.cancel("bob", r["id"]) is False  # outro usuario nao cancela
    assert store.ack("bob", r["id"]) is False
    assert store.cancel("ana", r["id"]) is True
    assert store.pending("ana") == []


def test_vencidos_so_depois_da_hora_e_ack_remove(store):
    r = store.add("ana", "ligar", NOW + timedelta(minutes=5))
    assert store.due("ana", NOW) == []
    assert [x["id"] for x in store.due("ana", NOW + timedelta(minutes=6))] == [r["id"]]
    assert store.due("bob", NOW + timedelta(hours=9)) == []
    assert store.ack("ana", r["id"], NOW + timedelta(minutes=6)) is True
    assert store.due("ana", NOW + timedelta(hours=9)) == [] and store.pending("ana") == []
    assert store.ack("ana", r["id"]) is False  # so uma vez


def test_lembrete_perdido_com_app_fechado_continua_na_fila(store):
    store.add("ana", "ligar", NOW)
    assert len(store.due("ana", NOW + timedelta(days=3))) == 1  # aparece quando o app abrir


def test_repetido_vai_para_a_proxima_ocorrencia(store):
    r = store.add("ana", "agua", NOW, repeat="daily")
    assert store.ack("ana", r["id"], NOW + timedelta(minutes=1))
    nxt = store.pending("ana")[0]
    assert datetime.fromisoformat(nxt["due_at"]) == NOW + timedelta(days=1)
    # app fechado por 3 dias: pula as ocorrencias perdidas, sem disparar 3 de uma vez
    assert store.ack("ana", r["id"], NOW + timedelta(days=3, hours=1))
    assert datetime.fromisoformat(store.pending("ana")[0]["due_at"]) == NOW + timedelta(days=4)


def test_validacoes(store):
    for bad in ({"user_id": "", "text": "x"}, {"user_id": "system", "text": "x"}, {"user_id": "ana", "text": "   "}):
        with pytest.raises(ValueError):
            store.add(bad["user_id"], bad["text"], NOW)
    with pytest.raises(ValueError):
        store.add("ana", "x", NOW, repeat="mensal")
    long = store.add("ana", "a" * 1000, NOW)
    assert len(long["text"]) == R.MAX_TEXT


def test_limite_de_pendentes(store, monkeypatch):
    monkeypatch.setattr(R, "MAX_PENDING", 3)
    for i in range(3):
        store.add("ana", f"t{i}", NOW)
    with pytest.raises(ValueError, match="limite"):
        store.add("ana", "outro", NOW)
    store.add("bob", "o limite e por usuario", NOW)


# ---------------- skill e rotas ----------------
def test_skill_responde_com_horario_e_pede_quando_falta(store):
    from src.jefrey.skills.reminders import ASK_WHEN, RemindersSkill
    sk = RemindersSkill()
    run = lambda name, **kw: asyncio.run(getattr(sk, name).ainvoke(kw))  # noqa: E731
    assert run("set_reminder", text="ligar", when="", user_id="ana") == ASK_WHEN
    out = run("set_reminder", text="ligar para a mae", when="amanha as 8h", user_id="ana")
    assert "ligar para a mae" in out and "08:00" in out
    assert "Assumi 9h" in run("set_reminder", text="x", when="amanha", user_id="ana")
    assert "ligar para a mae" in run("list_reminders", user_id="ana")
    assert "não tem lembretes" in run("list_reminders", user_id="bob")
    assert "quem você é" in run("set_reminder", text="x", when="amanha", user_id=None)


@pytest.fixture()
def client(store):
    from src.jefrey.api.main import app
    return TestClient(app), store


def _h(c, user):
    return {"Authorization": f"Bearer {c.post('/auth/dev-token', json={'user_id': user}).json()['access_token']}"}


def test_rotas_exigem_login(client):
    c, _ = client
    for path in ("/reminders", "/reminders/due"):
        assert c.get(path).status_code == 401


def test_rotas_fluxo_completo_e_isolamento(client):
    c, store = client
    ha, hb = _h(c, "ana"), _h(c, "bob")
    r = store.add("ana", "ligar", datetime.now(timezone.utc) - timedelta(minutes=1))
    assert c.get("/reminders/due", headers=ha).json()["count"] == 1
    assert c.get("/reminders/due", headers=hb).json()["count"] == 0
    assert c.post(f"/reminders/{r['id']}/ack", headers=hb).status_code == 404
    assert c.delete(f"/reminders/{r['id']}", headers=hb).status_code == 404
    assert c.post(f"/reminders/{r['id']}/ack", headers=ha).status_code == 200
    assert c.get("/reminders/due", headers=ha).json()["count"] == 0
    assert c.post(f"/reminders/{r['id']}/ack", headers=ha).status_code == 404

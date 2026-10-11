"""Sessao 13 (parte 1): termos, privacidade (LGPD): aceite, copia dos dados e apagar tudo de verdade."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.jefrey.core import privacy as P


@pytest.fixture()
def db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/s13.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    dbm.create_oauth2_tables()  # tokens do Google usam a sessao global (banco hermetico dos testes)
    from src.jefrey.core import google_oauth as G
    for u in ("ana", "bob", "apipriv"):
        G.delete_tokens(u)  # a sessao global e compartilhada entre os testes: comeca limpo
    return eng


class FakeLT:
    """Memoria de longo prazo falsa (isolada por pessoa), no lugar do Chroma."""

    def __init__(self):
        self.items = {}

    def add(self, uid, content):
        self.items[f"{uid}:{len(self.items)}"] = (uid, content)

    def list_recent(self, limit=20, filter_metadata=None, user_id=None):
        return [{"id": k, "content": c, "metadata": {"timestamp": "2026-10-01T10:00:00"}} for k, (u, c) in self.items.items() if u == user_id]

    def delete(self, mid, user_id=None):
        if mid in self.items and self.items[mid][0] == user_id:
            del self.items[mid]
            return True
        return False


@pytest.fixture()
def lt(monkeypatch):
    f = FakeLT()
    import src.jefrey.core.memory as M
    monkeypatch.setattr(M, "get_memory_manager", lambda: type("MM", (), {"long_term": f})())
    return f


def _povoar(user, lt):
    from src.jefrey.core import briefing, diary, learning, wa_web
    from src.jefrey.core.history import HistoryStore
    from src.jefrey.core.profile import ProfileStore
    from src.jefrey.core.reminders import ReminderStore
    from src.jefrey.core.studies import StudyStore
    ProfileStore().set_name(user, "Ana Souza")
    learning.FactStore().learn(user, learning.Fact("pessoa", "moradia", "Mora em Curitiba."))
    diary.DiaryStore().put(user, "2026-10-03", "Conversamos 2 vezes.")
    st = StudyStore()
    t = st.add_topic(user, "horta em casa")
    st.add_guide(user, t["id"], "Horta", "Comece pequeno.", "**Passo a passo**\n1. Sol", [{"title": "A", "url": "https://a.com", "date": "2026-10-04"}], 1)
    briefing.BriefingStore().put(user, "2026-10-04", "Bom dia, Ana!")
    HistoryStore().add_turn(user, f"{user}:t", "oi, tudo bem?", "tudo ótimo", now=datetime(2026, 10, 3, 12, 0))
    ReminderStore().add(user, "tomar o remédio", datetime(2026, 10, 5, 8, 0, tzinfo=ZoneInfo("America/Sao_Paulo")))
    wa = wa_web.WAStore()
    c = wa.touch_chat(user, "Maria")
    wa.add_draft(user, c, "oi", "oi!", "", "sent", ["m1"])
    lt.add(user, "A senha do wifi da casa de praia está na gaveta")


def test_textos_legais_empacotados_sem_comentarios_internos():
    d = P.documents()
    assert d["version"] == P.TERMS_VERSION
    for k in ("termos", "privacidade"):
        assert d[k].startswith("# ") and "<!--" not in d[k] and "REVISAR" not in d[k]
    assert "no seu computador" in d["privacidade"] and "Apagar tudo" in d["privacidade"] and "LGPD" in d["privacidade"]
    assert "bloqueio do número" in d["termos"] and "podem estar erradas" in d["termos"]


def test_aceite_por_pessoa_e_por_versao(db):
    s = P.ConsentStore()
    assert s.accepted("ana") is False
    s.accept("ana")
    s.accept("ana")  # idempotente
    assert s.accepted("ana") and not s.accepted("bob") and not s.accepted("ana", "1999-01-01")
    with pytest.raises(ValueError):
        s.accept("system")


def test_copia_dos_dados_traz_tudo_da_pessoa_e_nada_de_outra(db, lt):
    _povoar("ana", lt)
    _povoar("bob", lt)
    lt.add("bob", "segredo do bob")
    d = P.export_all("ana")
    assert d["nome"] == "Ana Souza" and d["o_que_aprendi"][0]["texto"] == "Mora em Curitiba."
    assert d["diario"][0]["summary"] == "Conversamos 2 vezes." and d["estudos"][0]["assunto"] == "horta em casa" and "Passo a passo" in d["estudos"][0]["guia"]
    assert d["resumos_da_manha"][0]["texto"] == "Bom dia, Ana!" and d["lembretes_pendentes"][0]["texto"] == "tomar o remédio"
    assert [m["texto"] for m in d["memorias_e_notas"]] == ["A senha do wifi da casa de praia está na gaveta"]
    assert d["conversas"][0]["quem"] == "voce" and d["whatsapp"]["respostas"][0]["resposta"] == "oi!"
    assert d["pessoa"] == "ana"
    assert "segredo do bob" not in json.dumps(d, ensure_ascii=False)


def test_a_copia_nunca_inclui_tokens_nem_chaves(db, lt):
    from src.jefrey.core import google_oauth as G
    G.save_tokens("ana", ["calendar"], {"access_token": "AT-super-secreto", "refresh_token": "RT-super-secreto"}, "ana@exemplo.com")
    txt = json.dumps(P.export_all("ana"), ensure_ascii=False)
    assert "super-secreto" not in txt and "ana@exemplo.com" in txt and '"conectado": true' in txt


def test_resumo_so_conta(db, lt):
    _povoar("ana", lt)
    s = P.summary("ana")
    assert s == {"nome": True, "fatos": 1, "diario": 1, "assuntos": 1, "lembretes": 1, "memorias": 1, "mensagens": 2, "whatsapp": 1, "google": False}


def test_apagar_tudo_remove_de_verdade_e_so_da_pessoa(db, lt):
    from src.jefrey.core import google_oauth as G
    _povoar("ana", lt)
    _povoar("bob", lt)
    G.save_tokens("ana", ["calendar", "email"], {"access_token": "AT", "refresh_token": "RT"}, "ana@exemplo.com")
    P.ConsentStore().accept("ana")
    res = P.erase_all("ana")
    assert res["fatos"] == 1 and res["diario"] == 1 and res["estudos"] == 1 and res["mensagens"] == 2 and res["lembretes"] == 1 and res["memorias"] == 1
    assert res["_google_tokens"] == ["RT"]
    vazio = P.summary("ana")
    assert vazio == {"nome": False, "fatos": 0, "diario": 0, "assuntos": 0, "lembretes": 0, "memorias": 0, "mensagens": 0, "whatsapp": 0, "google": False}
    assert P.summary("bob")["fatos"] == 1 and P.summary("bob")["memorias"] == 1 and P.summary("bob")["nome"] is True  # o outro nao foi tocado
    assert P.ConsentStore().accepted("ana") is True  # o aceite (registro legal) continua
    assert P.erase_all("ana")["fatos"] == 0  # apagar de novo nao quebra


def test_uma_parte_quebrada_nao_impede_de_apagar_o_resto(db, lt, monkeypatch):
    _povoar("ana", lt)
    import src.jefrey.core.diary as D
    monkeypatch.setattr(D.DiaryStore, "forget_all", lambda self, u: (_ for _ in ()).throw(RuntimeError("falha")))
    res = P.erase_all("ana")
    assert res["diario"] == 0 and res["fatos"] == 1 and res["memorias"] == 1


# ---------------- API ----------------
@pytest.fixture()
def api(db, lt):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apipriv"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}, lt


def test_api_exige_login(api):
    c, h, lt = api
    for m, p in [("get", "/legal/documents"), ("get", "/legal/status"), ("post", "/legal/accept"), ("get", "/privacy/summary"),
                 ("get", "/privacy/export"), ("post", "/privacy/erase")]:
        assert getattr(c, m)(p).status_code == 401, p


def test_api_aceite_copia_e_apagar(api, monkeypatch):
    c, h, lt = api
    assert c.get("/legal/status", headers=h).json() == {"accepted": False, "version": P.TERMS_VERSION}
    assert c.get("/legal/documents", headers=h).json()["termos"].startswith("# Termos")
    assert c.post("/legal/accept", headers=h).json()["accepted"] is True
    assert c.get("/legal/status", headers=h).json()["accepted"] is True
    _povoar("apipriv", lt)
    r = c.get("/privacy/export", headers=h)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    assert r.json()["nome"] == "Ana Souza" and c.get("/privacy/summary", headers=h).json()["fatos"] == 1
    # apagar exige a palavra
    assert c.post("/privacy/erase", headers=h, json={"confirm": "sim"}).status_code == 422
    assert c.get("/privacy/summary", headers=h).json()["fatos"] == 1
    import src.jefrey.api.privacy_routes as PR
    revogados = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **k):
            revogados.append(data["token"])

    monkeypatch.setattr(__import__("httpx"), "AsyncClient", FakeClient)
    from src.jefrey.core import google_oauth as G
    G.save_tokens("apipriv", ["calendar"], {"access_token": "AT", "refresh_token": "RT-revogar"}, None)
    out = c.post("/privacy/erase", headers=h, json={"confirm": " apagar "}).json()
    assert out["ok"] is True and out["apagado"]["fatos"] == 1 and "_google_tokens" not in out["apagado"] and revogados == ["RT-revogar"]
    assert c.get("/privacy/summary", headers=h).json()["fatos"] == 0
    assert c.get("/legal/status", headers=h).json()["accepted"] is True

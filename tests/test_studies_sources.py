"""Fontes indicadas pela pessoa (links para pesquisar) e "aprender por pedido" sem usar o chat."""
import asyncio
import json
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.jefrey.core import studies as S

TZ = ZoneInfo("America/Sao_Paulo")
PAGINA = "Escolha um lugar com sol para a horta e regue de manhã cedo todos os dias. " * 5


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/src.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    return eng


class FakeCloud:
    def __init__(self, cloud=True):
        self.config = type("C", (), {"is_cloud": cloud})()
        self.n = 0
        self.guia = json.dumps({"title": "Guia", "summary": "Comece pequeno.", "steps": ["Escolha um lugar com sol [1]", "Regue de manhã [1]"],
                                "tips": ["Comece com alface"], "cautions": [], "used": [1, 2, 3]})

    async def chat(self, messages):
        self.n += 1
        return '{"queries": ["horta", "como regar", "erros"]}' if self.n == 1 else self.guia


async def fake_search(q, n):
    return [{"title": "A", "url": "https://a.com/horta", "snippet": ""}]


async def fake_fetch(url):
    return {"url": url, "title": "Pagina " + url[-6:], "text": PAGINA, "fetched_at": "2026-10-04"}


def test_fonte_da_pessoa_e_lida_primeiro_e_vai_marcada_no_guia(db):
    st = S.StudyStore()
    t = st.add_topic("ana", "horta em casa")
    st.add_source("ana", "https://meusite.com.br/guia-horta", t["id"], "Guia da vizinha")
    lidas = []

    async def anota(url):
        lidas.append(url)
        return await fake_fetch(url)
    g = run(S.study_topic("ana", t["id"], FakeCloud(), tz=TZ, search=fake_search, fetch=anota, store=st))
    assert lidas[0] == "https://meusite.com.br/guia-horta"
    assert any(s.get("mine") and s["url"] == "https://meusite.com.br/guia-horta" for s in g["sources"])
    assert not any(s.get("mine") for s in g["sources"] if s["url"] == "https://a.com/horta")


@pytest.mark.parametrize("ruim", ["javascript:alert(1)", "file:///C:/x", "http://localhost:8000/x", "http://192.168.0.1", "https://user:senha@x.com", "palavra", ""])
def test_fonte_com_link_perigoso_e_recusada(db, ruim):
    with pytest.raises(ValueError, match="link"):
        S.StudyStore().add_source("ana", ruim)


def test_fontes_isoladas_sem_duplicar_com_limite_e_apagaveis(db):
    st = S.StudyStore()
    a = st.add_source("ana", "https://a.com/x")
    assert st.add_source("ana", "https://a.com/x")["id"] == a["id"]
    assert st.list_sources("bob") == [] and st.delete_source("bob", a["id"]) is False
    for i in range(S.MAX_SOURCES - 1):
        st.add_source("ana", f"https://site{i}.com/p")
    with pytest.raises(ValueError, match="fontes"):
        st.add_source("ana", "https://excedente.com/p")
    assert st.delete_source("ana", a["id"]) is True
    t = st.add_topic("ana", "violão")
    st.add_source("ana", "https://musica.com/v", t["id"])
    st.delete_topic("ana", t["id"])
    assert all(s["topic_id"] != t["id"] for s in st.list_sources("ana"))
    st.forget_all("ana")
    assert st.list_sources("ana") == []


def test_aprender_por_link_cria_assunto_com_o_titulo_da_pagina(db):
    async def pagina(url):
        return {"url": url, "title": "Como cuidar de orquídeas | Blog X", "text": "x" * 300, "fetched_at": "2026-10-04"}
    out = run(S.learn_request("ana", url="https://blog.exemplo.com/orquideas", fetch=pagina))
    assert out["topic"]["title"] == "Como cuidar de orquídeas" and out["source"] == "https://blog.exemplo.com/orquideas"
    again = run(S.learn_request("ana", url="https://blog.exemplo.com/outra", topic="Como cuidar de orquídeas", fetch=pagina))
    assert again["topic"]["id"] == out["topic"]["id"] and len(S.StudyStore().list_sources("ana")) == 2


def test_aprender_por_assunto_repetido_nao_quebra(db):
    a = run(S.learn_request("ana", topic="jardinagem"))
    b = run(S.learn_request("ana", topic="Jardinagem"))
    assert a["topic"]["id"] == b["topic"]["id"]


def test_aprender_por_texto_guarda_nota_e_fatos_sem_segredos(db, monkeypatch):
    notas = []
    import src.jefrey.core.memory as M

    class LT:
        def add(self, c, metadata=None, user_id=None):
            notas.append((user_id, c, metadata))
    monkeypatch.setattr(M, "get_memory_manager", lambda: type("MM", (), {"long_term": LT()})())
    out = run(S.learn_request("ana", text="Eu moro em Recife e meu aniversário é dia 4 de outubro. Anote isso para mim."))
    assert out["saved_text"] is True and out["facts"] == 2 and notas[0][0] == "ana" and notas[0][2]["source"] == "aprender"
    with pytest.raises(ValueError, match="senha"):
        run(S.learn_request("ana", text="minha senha do banco é 1234 e o cpf 123.456.789-09 para guardar"))
    assert len(notas) == 1


def test_pedido_vazio_ou_link_ruim_explica(db):
    with pytest.raises(ValueError, match="Diga o assunto"):
        run(S.learn_request("ana"))
    with pytest.raises(ValueError, match="link"):
        run(S.learn_request("ana", url="javascript:alert(1)"))


@pytest.fixture()
def client(db):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apisrc"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def test_api_aprender_e_fontes(client, monkeypatch):
    c, h = client
    import src.jefrey.core.llm_provider as LP
    monkeypatch.setattr(LP, "get_llm_client", lambda: FakeCloud())
    monkeypatch.setattr(S.webread, "web_search", fake_search)
    monkeypatch.setattr(S.webread, "fetch_page", fake_fetch)
    assert c.post("/studies/learn", json={"topic": "x y z"}).status_code == 401
    assert c.post("/studies/learn", headers=h, json={}).status_code == 422
    r = c.post("/studies/learn", headers=h, json={"topic": "pintura a óleo", "url": "https://arte.exemplo.com/oleo", "run": True}).json()
    assert r["topic"]["title"] == "pintura a óleo" and r["guide"]["level"] == 1 and r["guide"]["sources"]
    src = c.get("/studies/sources", headers=h).json()["sources"]
    assert src[0]["url"] == "https://arte.exemplo.com/oleo"
    add = c.post(f"/studies/{r['topic']['id']}/sources", headers=h, json={"url": "pt.wikipedia.org/wiki/Pintura"}).json()
    assert add["url"] == "https://pt.wikipedia.org/wiki/Pintura"
    assert c.post(f"/studies/{r['topic']['id']}/sources", headers=h, json={"url": "file:///C:/x"}).status_code == 422
    assert c.delete(f"/studies/sources/{add['id']}", headers=h).json() == {"ok": True}
    assert c.delete(f"/studies/sources/{add['id']}", headers=h).status_code == 404
    monkeypatch.setattr(LP, "get_llm_client", lambda: FakeCloud(cloud=False))
    r2 = c.post("/studies/learn", headers=h, json={"topic": "cerâmica", "run": True}).json()
    assert r2["topic"]["title"] == "cerâmica" and "nuvem" in r2["run_error"] and "guide" not in r2

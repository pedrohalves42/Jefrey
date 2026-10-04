"""Memoria de longo prazo: isolamento entre usuarios em add/update/delete/list e nos endpoints."""
import hashlib
import math
import uuid

import chromadb
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app
from src.jefrey.core.memory import LongTermMemory


class FakeEmbeddings:
    """Embedding deterministico (hash de palavras): textos parecidos ficam proximos."""

    def _vec(self, text: str):
        v = [0.0] * 64
        for w in text.lower().split():
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            v[h % 64] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_query(self, text: str):
        return self._vec(text)

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]


@pytest.fixture()
def ltm():
    client = chromadb.EphemeralClient()
    name = "t" + uuid.uuid4().hex[:10]
    col = client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
    m = LongTermMemory.__new__(LongTermMemory)
    m._top_k, m._similarity_threshold = 5, 0.1
    m._embeddings, m._collection = FakeEmbeddings(), col
    return m


# ---------------- add ----------------
def test_user_id_do_servidor_vence_o_metadata(ltm):
    mid = ltm.add("segredo", metadata={"user_id": "vitima"}, user_id="invasor")
    assert ltm.get(mid, user_id="invasor")["metadata"]["user_id"] == "invasor"
    assert ltm.get(mid, user_id="vitima") is None


def test_add_nao_muta_o_dict_do_chamador(ltm):
    meta = {"tag": "x"}
    ltm.add("a", metadata=meta, user_id="ana")
    assert meta == {"tag": "x"}


# ---------------- update ----------------
def test_so_o_dono_atualiza(ltm):
    mid = ltm.add("original", user_id="ana")
    assert ltm.update(mid, content="invadido", user_id="bob") is False
    assert ltm.get(mid, user_id="ana")["content"] == "original"
    assert ltm.update(mid, content="novo", user_id="ana") is True
    assert ltm.get(mid, user_id="ana")["content"] == "novo"


def test_update_nao_deixa_trocar_o_dono_pelo_metadata(ltm):
    mid = ltm.add("meu", user_id="ana")
    assert ltm.update(mid, metadata={"user_id": "bob", "tag": "t"}, user_id="ana") is True
    assert ltm.get(mid, user_id="ana") is not None  # continua da ana
    assert ltm.get(mid, user_id="bob") is None
    assert ltm.get(mid, user_id="ana")["metadata"]["tag"] == "t"


# ---------------- delete ----------------
def test_so_o_dono_apaga(ltm):
    mid = ltm.add("a", user_id="ana")
    assert ltm.delete(mid, user_id="bob") is False
    assert ltm.get(mid, user_id="ana") is not None
    assert ltm.delete(mid, user_id="ana") is True
    assert ltm.get(mid, user_id="ana") is None


# ---------------- listagem e busca ----------------
def test_list_recent_isola_e_ordena_do_mais_novo(ltm):
    ids = []
    for i in range(5):
        ids.append(ltm.add(f"nota {i}", metadata={"timestamp": f"2026-01-0{i + 1}T10:00:00"}, user_id="ana"))
    ltm.add("de outro", user_id="bob")
    out = ltm.list_recent(limit=3, user_id="ana")
    assert [m["content"] for m in out] == ["nota 4", "nota 3", "nota 2"]
    assert all(m["metadata"]["user_id"] == "ana" for m in out)


def test_busca_so_acha_do_proprio_usuario(ltm):
    ltm.add("codigo do cofre zeta", user_id="ana")
    assert ltm.search("codigo do cofre zeta", user_id="bob") == []
    assert len(ltm.search("codigo do cofre zeta", user_id="ana")) == 1


# ---------------- endpoints ----------------
@pytest.fixture()
def client(ltm, monkeypatch):
    from src.jefrey.api import memory as api_memory

    class FakeManager:
        long_term = ltm
    monkeypatch.setattr(api_memory, "get_memory_manager", lambda: FakeManager())
    return TestClient(app)


def _h(client, user):
    r = client.post("/auth/dev-token", json={"user_id": user})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_endpoints_exigem_login(client):
    assert client.get("/memory/recent").status_code == 401
    assert client.delete("/memory/abcdefgh1234").status_code == 401


def test_add_devolve_id_completo_e_o_dono_consegue_apagar(client):
    h = _h(client, "ana")
    r = client.post("/memory/add", headers=h, json={"content": "meu segredo", "title": "T"})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert len(mid) == 36  # UUID inteiro, nao truncado
    rec = client.get("/memory/recent", headers=h).json()
    assert [m["id"] for m in rec["memories"]] == [mid]
    assert rec["memories"][0]["metadata"]["title"] == "T"
    assert client.delete(f"/memory/{mid}", headers=h).status_code == 200
    assert client.get("/memory/recent", headers=h).json()["count"] == 0


def test_outro_usuario_nao_apaga_nem_ve(client):
    ha, hb = _h(client, "ana"), _h(client, "bob")
    mid = client.post("/memory/add", headers=ha, json={"content": "da ana"}).json()["id"]
    assert client.delete(f"/memory/{mid}", headers=hb).status_code == 404
    assert client.get("/memory/recent", headers=hb).json()["count"] == 0
    assert client.get("/memory/recent", headers=ha).json()["count"] == 1


def test_id_invalido_e_rejeitado(client):
    h = _h(client, "ana")
    assert client.delete("/memory/abc", headers=h).status_code == 400
    assert client.delete("/memory/..%2F..%2Fetc", headers=h).status_code in (400, 404, 405)  # nunca 200


def test_add_valida_entrada(client):
    h = _h(client, "ana")
    assert client.post("/memory/add", headers=h, json={"content": "   "}).status_code == 400
    assert client.post("/memory/add", headers=h, data="nao json").status_code == 400

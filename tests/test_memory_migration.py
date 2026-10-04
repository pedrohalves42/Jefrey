"""Troca do modelo de embedding: colecao por modelo, migracao automatica e provedor independente do chat."""
import hashlib
import math
import uuid

import chromadb
import pytest

from src.jefrey.core.memory import (
    LEGACY_EMBEDDING_MODEL, LongTermMemory, collection_name_for, reindex_collection,
)


class Emb:
    """Embedding falso; `salt` muda o espaco vetorial (simula outro modelo)."""

    def __init__(self, salt="a"):
        self.salt, self.calls, self.fail = salt, 0, False

    def _v(self, text):
        v = [0.0] * 64
        for w in text.lower().split():
            v[int(hashlib.md5((self.salt + w).encode()).hexdigest(), 16) % 64] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_query(self, t):
        return self._v(t)

    def embed_documents(self, ts):
        self.calls += 1
        if self.fail:
            raise ConnectionError("ollama fora")
        return [self._v(t) for t in ts]


def new_col(client, name):
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def make_ltm(old, new, emb):
    m = LongTermMemory.__new__(LongTermMemory)
    m._top_k, m._similarity_threshold = 5, 0.0
    m._embeddings, m._collection, m._legacy, m._legacy_checked = emb, new, old, False
    return m


@pytest.fixture()
def client():
    return chromadb.EphemeralClient()


def uid():
    return "c" + uuid.uuid4().hex[:10]


# ---------------- nome da colecao ----------------
def test_modelo_legado_mantem_o_nome_original():
    assert collection_name_for("jefrey_memory", LEGACY_EMBEDDING_MODEL) == "jefrey_memory"
    assert collection_name_for("jefrey_memory", "") == "jefrey_memory"


def test_modelo_novo_ganha_sufixo_valido_para_o_chroma():
    n = collection_name_for("jefrey_memory", "embeddinggemma")
    assert n == "jefrey_memory__embeddinggemma"
    odd = collection_name_for("jefrey_memory", "org/Modelo Estranho:1.5b!!")
    assert 3 <= len(odd) <= 63 and all(c.isalnum() or c in "_-" for c in odd)
    assert collection_name_for("x" * 80, "m" * 80) and len(collection_name_for("x" * 80, "m" * 80)) <= 63


def test_modelos_diferentes_nunca_compartilham_colecao():
    assert collection_name_for("b", "embeddinggemma") != collection_name_for("b", "bge-m3")


# ---------------- reindexacao ----------------
def test_reindex_copia_tudo_com_ids_e_metadados(client):
    old, new = new_col(client, uid()), new_col(client, uid())
    old.add(ids=["a", "b", "c"], documents=["um", "dois", "tres"],
            metadatas=[{"user_id": "ana"}, {"user_id": "ana"}, {"user_id": "bob"}],
            embeddings=[Emb("velho")._v(t) for t in ("um", "dois", "tres")])
    assert reindex_collection(old, new, Emb("novo").embed_documents, batch=2) == 3
    got = new.get(include=["documents", "metadatas"])
    assert sorted(got["ids"]) == ["a", "b", "c"]
    assert {i: m["user_id"] for i, m in zip(got["ids"], got["metadatas"])} == {"a": "ana", "b": "ana", "c": "bob"}


def test_reindex_e_idempotente(client):
    old, new = new_col(client, uid()), new_col(client, uid())
    old.add(ids=["a"], documents=["um"], metadatas=[{"user_id": "ana"}], embeddings=[Emb("v")._v("um")])
    e = Emb("n")
    reindex_collection(old, new, e.embed_documents)
    reindex_collection(old, new, e.embed_documents)
    assert new.count() == 1


# ---------------- migracao automatica ----------------
def test_migra_na_primeira_busca_e_o_isolamento_continua(client):
    old, new = new_col(client, uid()), new_col(client, uid())
    for i, (text, user) in enumerate([("cafe sem acucar", "ana"), ("segredo do bob", "bob")]):
        old.add(ids=[f"id{i}"], documents=[text], metadatas=[{"user_id": user}], embeddings=[Emb("velho")._v(text)])
    ltm = make_ltm(old, new, Emb("novo"))
    assert ltm.migrate_legacy() == 2
    assert [r["content"] for r in ltm.search("cafe sem acucar", user_id="ana")] == ["cafe sem acucar"]
    # isolamento preservado apos migrar: a Ana nunca recebe nada que pertence ao Bob
    assert all(r["metadata"]["user_id"] == "ana" and "bob" not in r["content"]
               for r in ltm.search("segredo do bob", user_id="ana"))
    assert ltm.count(user_id="bob") == 1


def test_nao_migra_de_novo_depois_de_migrado(client):
    old, new = new_col(client, uid()), new_col(client, uid())
    old.add(ids=["a"], documents=["x"], metadatas=[{"user_id": "ana"}], embeddings=[Emb("v")._v("x")])
    e = Emb("n")
    ltm = make_ltm(old, new, e)
    assert ltm.migrate_legacy() == 1
    calls = e.calls
    assert ltm.migrate_legacy() == 0 and e.calls == calls  # nem chamou o modelo


def test_falha_do_modelo_adia_a_migracao_e_tenta_de_novo(client):
    old, new = new_col(client, uid()), new_col(client, uid())
    old.add(ids=["a"], documents=["x"], metadatas=[{"user_id": "ana"}], embeddings=[Emb("v")._v("x")])
    e = Emb("n")
    e.fail = True
    ltm = make_ltm(old, new, e)
    assert ltm.migrate_legacy() == 0  # nao levanta excecao
    assert new.count() == 0 and ltm._legacy_checked is False
    e.fail = False
    assert ltm.migrate_legacy() == 1 and new.count() == 1


def test_sem_colecao_antiga_nao_faz_nada(client):
    ltm = make_ltm(None, new_col(client, uid()), Emb())
    assert ltm.migrate_legacy() == 0


def test_colecao_nova_completa_nao_reindexa(client):
    old, new = new_col(client, uid()), new_col(client, uid())
    old.add(ids=["a"], documents=["x"], metadatas=[{"user_id": "ana"}], embeddings=[Emb("v")._v("x")])
    new.add(ids=["a"], documents=["x"], metadatas=[{"user_id": "ana"}], embeddings=[Emb("n")._v("x")])
    e = Emb("n")
    assert make_ltm(old, new, e).migrate_legacy() == 0 and e.calls == 0


# ---------------- provedor de embeddings independente do chat ----------------
def test_embeddings_seguem_local_mesmo_com_chat_na_nuvem(monkeypatch):
    from src.jefrey.core import memory as mem
    from src.jefrey.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.llm, "provider", "anthropic")
    obj = mem._create_embeddings()
    # embeddings tem escolha propria (Ollama -> nuvem do usuario -> motor local), independente do provedor do chat
    assert type(obj).__name__ == "AutoEmbeddings"

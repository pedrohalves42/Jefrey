"""Embeddings sem depender do Ollama: backends, escolha automatica, escolha fixa e degradacao sem erro 500."""
import json

import chromadb
import httpx
import pytest

from src.jefrey.core import embeddings as E
from src.jefrey.core.embeddings import (
    AutoEmbeddings, Choice, ChromaDefaultEmbeddings, EmbeddingsUnavailable, HttpEmbeddings, cloud_choice,
)

VEC = [0.1] * 16


def ollama_transport(model_ok=True):
    def h(req):
        body = json.loads(req.content)
        if not model_ok:
            return httpx.Response(404, json={"error": "model not found"})
        return httpx.Response(200, json={"embeddings": [VEC for _ in body["input"]]})
    return httpx.MockTransport(h)


def openai_transport(status=200):
    seen = {}

    def h(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers.get("authorization"), json.loads(req.content)
        if status != 200:
            return httpx.Response(status)
        n = len(seen["body"]["input"])
        # devolve fora de ordem para provar que o indice e respeitado
        data = [{"index": i, "embedding": [float(i)] * 16} for i in reversed(range(n))]
        return httpx.Response(200, json={"data": data})
    return httpx.MockTransport(h), seen


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    return tmp_path


# ---------------- backends ----------------
def test_ollama_em_lotes_e_vetores_corretos():
    emb = HttpEmbeddings(Choice("ollama", "embeddinggemma", "http://x:11434"), transport=ollama_transport())
    out = emb.embed_documents([f"t{i}" for i in range(70)])
    assert len(out) == 70 and all(len(v) == 16 for v in out)
    assert emb.embed_query("oi") == VEC


def test_openai_compativel_usa_chave_url_certa_e_respeita_o_indice():
    tr, seen = openai_transport()
    emb = HttpEmbeddings(Choice("openai", "baai/bge-m3", "https://openrouter.ai/api"), api_key="sk-or-1", transport=tr)
    out = emb.embed_documents(["a", "b", "c"])
    assert seen["url"] == "https://openrouter.ai/api/v1/embeddings" and seen["auth"] == "Bearer sk-or-1"
    assert seen["body"] == {"model": "baai/bge-m3", "input": ["a", "b", "c"]}
    assert [v[0] for v in out] == [0.0, 1.0, 2.0]  # voltou fora de ordem, saiu na ordem certa


@pytest.mark.parametrize("status,trecho", [(401, "chave recusada"), (403, "chave recusada"), (404, "nao encontrado"),
                                           (429, "limite de uso"), (500, "HTTP 500")])
def test_falhas_http_viram_mensagem_clara_sem_vazar_chave(status, trecho):
    tr, _ = openai_transport(status)
    emb = HttpEmbeddings(Choice("openai", "m", "https://api.openai.com"), api_key="sk-segredo", transport=tr)
    with pytest.raises(EmbeddingsUnavailable) as ei:
        emb.embed_query("x")
    assert trecho in str(ei.value) and "sk-segredo" not in str(ei.value) and "api.openai.com" not in str(ei.value)


def test_servico_fora_do_ar_e_resposta_estranha():
    def down(req):
        raise httpx.ConnectError("recusou")
    with pytest.raises(EmbeddingsUnavailable, match="ConnectError"):
        HttpEmbeddings(Choice("ollama", "m", "http://x"), transport=httpx.MockTransport(down)).embed_query("x")
    bad = httpx.MockTransport(lambda r: httpx.Response(200, json={"foo": 1}))
    with pytest.raises(EmbeddingsUnavailable, match="inesperada"):
        HttpEmbeddings(Choice("ollama", "m", "http://x"), transport=bad).embed_query("x")
    short = httpx.MockTransport(lambda r: httpx.Response(200, json={"embeddings": [VEC]}))
    with pytest.raises(EmbeddingsUnavailable, match="incompleta"):
        HttpEmbeddings(Choice("ollama", "m", "http://x"), transport=short).embed_documents(["a", "b"])


def test_motor_embutido_do_chroma_com_fabrica_falsa():
    fake = lambda texts: [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0] for _ in texts]  # noqa: E731
    emb = ChromaDefaultEmbeddings(factory=lambda: fake)
    assert emb.embed_documents(["a", "b"])[0][0] == 1.0 and emb.model_id == "chroma-default"

    def explode():
        raise OSError("sem internet para baixar o modelo")
    with pytest.raises(EmbeddingsUnavailable):
        ChromaDefaultEmbeddings(factory=explode).embed_query("x")


def test_model_id_mantem_o_nome_do_ollama_e_distingue_nuvem():
    assert Choice("ollama", "embeddinggemma").model_id == "embeddinggemma"  # preserva colecoes antigas
    assert Choice("openai", "baai/bge-m3", "https://openrouter.ai/api").model_id == "openrouter-baai/bge-m3"
    assert Choice("openai", "text-embedding-3-small", "https://api.openai.com").model_id == "openai-text-embedding-3-small"
    assert Choice("chroma", "x").model_id == "chroma-default"


def test_cloud_choice_so_para_nuvens_com_servico():
    assert cloud_choice("https://openrouter.ai/api", "k") == Choice("openai", "baai/bge-m3", "https://openrouter.ai/api")
    assert cloud_choice("https://api.openai.com", "k").model == "text-embedding-3-small"
    assert cloud_choice("https://api.anthropic.com", "k") is None  # a Anthropic nao tem embeddings
    assert cloud_choice("https://openrouter.ai/api", None) is None and cloud_choice("", "k") is None


# ---------------- escolha automatica ----------------
def fake_builder(works: dict):
    class Impl:
        def __init__(self, choice):
            self.choice, self.model_id = choice, choice.model_id

        def embed_query(self, t):
            if not works.get(self.choice.backend, False):
                raise EmbeddingsUnavailable("fora")
            return VEC

        def embed_documents(self, ts):
            return [self.embed_query(t) for t in ts]
    return lambda choice, key: Impl(choice)


CANDS = lambda: [(Choice("ollama", "embeddinggemma", "http://x"), None),  # noqa: E731
                 (Choice("openai", "baai/bge-m3", "https://openrouter.ai/api"), "k"),
                 (Choice("chroma", "all-MiniLM-L6-v2"), None)]


def test_prefere_ollama_e_grava_a_escolha():
    a = AutoEmbeddings(CANDS, builder=fake_builder({"ollama": True, "openai": True, "chroma": True}))
    assert a.model_id == "embeddinggemma"
    assert E.load_choice() == Choice("ollama", "embeddinggemma", "http://x")


def test_sem_ollama_usa_a_nuvem_e_sem_nuvem_usa_o_motor_embutido():
    assert AutoEmbeddings(CANDS, builder=fake_builder({"ollama": False, "openai": True, "chroma": True})).model_id == "openrouter-baai/bge-m3"
    E.forget_choice()
    assert AutoEmbeddings(CANDS, builder=fake_builder({"ollama": False, "openai": False, "chroma": True})).model_id == "chroma-default"


def test_sem_nenhum_backend_levanta_mensagem_clara():
    a = AutoEmbeddings(CANDS, builder=fake_builder({}))
    with pytest.raises(EmbeddingsUnavailable) as ei:
        a.embed_query("x")
    assert "Configurações" in str(ei.value) and E.load_choice() is None


def test_escolha_gravada_que_cai_usa_outra_so_por_enquanto_sem_trocar_a_gravada():
    """Antes: o Ollama desligado deixava a memoria MORTA para sempre. Agora: usa a nuvem/motor embutido enquanto ele estiver fora."""
    E.save_choice(Choice("ollama", "embeddinggemma", "http://x"))
    a = AutoEmbeddings(CANDS, builder=fake_builder({"ollama": False, "openai": True, "chroma": True}))
    assert a.model_id == "openrouter-baai/bge-m3"  # outra colecao: nada se mistura
    assert a.fallback_from == "ollama/embeddinggemma"
    assert E.load_choice().backend == "ollama"  # a escolha gravada continua sendo o Ollama


def test_gravada_que_cai_sem_nenhuma_alternativa_continua_indisponivel():
    E.save_choice(Choice("ollama", "embeddinggemma", "http://x"))
    a = AutoEmbeddings(CANDS, builder=fake_builder({"ollama": False, "openai": False, "chroma": False}))
    with pytest.raises(EmbeddingsUnavailable):
        a.model_id
    assert E.load_choice().backend == "ollama"


def test_quando_a_gravada_volta_as_memorias_antigas_voltam():
    E.save_choice(Choice("ollama", "embeddinggemma", "http://x"))
    works = {"ollama": False, "openai": True, "chroma": True}
    assert AutoEmbeddings(CANDS, builder=fake_builder(works)).model_id == "openrouter-baai/bge-m3"
    works["ollama"] = True
    b = AutoEmbeddings(CANDS, builder=fake_builder(works))
    assert b.model_id == "embeddinggemma" and b.fallback_from is None


def test_modo_servidor_nao_grava_escolha(monkeypatch):
    a = AutoEmbeddings(lambda: [(Choice("ollama", "embeddinggemma", "http://x"), None)], auto=False,
                       builder=fake_builder({"ollama": True}))
    assert a.model_id == "embeddinggemma" and E.load_choice() is None


def test_vetor_invalido_no_teste_de_conexao_e_recusado():
    class Bad:
        model_id = "x"

        def embed_query(self, t):
            return [0.1, 0.2]  # curto demais
    a = AutoEmbeddings(lambda: [(Choice("ollama", "m"), None)], builder=lambda c, k: Bad())
    with pytest.raises(EmbeddingsUnavailable):
        a.model_id


def test_arquivo_de_escolha_corrompido_e_ignorado(cfg):
    (cfg / "embeddings.runtime.json").write_text("{lixo", encoding="utf-8")
    assert E.load_choice() is None
    (cfg / "embeddings.runtime.json").write_text(json.dumps({"backend": "invalido", "model": "x"}), encoding="utf-8")
    assert E.load_choice() is None


# ---------------- integracao com a memoria ----------------
class FakeBackend:
    """Comporta-se como o AutoEmbeddings real: sem backend, ate descobrir o modelo falha."""

    def __init__(self, ok=True, mid="fake-1"):
        self.ok, self._mid = ok, mid

    @property
    def model_id(self):
        if not self.ok:
            raise EmbeddingsUnavailable(E.UNAVAILABLE_MSG)
        return self._mid

    def embed_query(self, t):
        if not self.ok:
            raise EmbeddingsUnavailable(E.UNAVAILABLE_MSG)
        return [float(len(t) % 7 + 1)] * 16

    def embed_documents(self, ts):
        return [self.embed_query(t) for t in ts]


def make_ltm(monkeypatch, backend):
    from src.jefrey.core import memory as mem
    from src.jefrey.core.memory import LongTermMemory
    monkeypatch.setattr(mem, "get_embeddings", lambda: backend)
    monkeypatch.setattr(mem.ChromaConnectionPool, "get_collection",
                        lambda self, name, _c={}: _c.setdefault(name, chromadb.EphemeralClient().get_or_create_collection(
                            "t" + str(abs(hash(name)))[:8], metadata={"hnsw:space": "cosine"})))
    return LongTermMemory()


def test_memoria_sem_backend_nao_quebra_a_construcao_e_diz_o_motivo(monkeypatch):
    ltm = make_ltm(monkeypatch, FakeBackend(ok=False))
    assert ltm.available is False
    with pytest.raises(EmbeddingsUnavailable):
        ltm.add("oi", user_id="ana")
    with pytest.raises(EmbeddingsUnavailable):
        ltm.search("oi", user_id="ana")


def test_memoria_volta_sozinha_quando_o_backend_aparece(monkeypatch):
    b = FakeBackend(ok=False, mid="fake-2")
    ltm = make_ltm(monkeypatch, b)
    assert ltm.available is False
    b.ok = True  # a pessoa colou uma chave
    mid = ltm.add("meu nome e Carla", user_id="ana")
    assert ltm.get(mid, user_id="ana")["content"] == "meu nome e Carla"


def test_cache_separa_espacos_vetoriais(monkeypatch):
    from src.jefrey.core.memory import CachedEmbeddings
    a, b = FakeBackend(mid="m-a"), FakeBackend(mid="m-b")
    b.embed_query = lambda t: [9.0] * 16
    assert CachedEmbeddings(a).embed_query("mesmo texto") != CachedEmbeddings(b).embed_query("mesmo texto")
    assert CachedEmbeddings(b).embed_documents(["mesmo texto"])[0] == [9.0] * 16


# ---------------- API ----------------
def test_api_devolve_503_claro_sem_backend(monkeypatch):
    from fastapi.testclient import TestClient
    from src.jefrey.api import memory as api_memory
    from src.jefrey.api.main import app
    ltm = make_ltm(monkeypatch, FakeBackend(ok=False))
    monkeypatch.setattr(api_memory, "get_memory_manager", lambda: type("M", (), {"long_term": ltm})())
    from src.jefrey.api import auth_middleware
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    h = {"Authorization": "Bearer " + c.post("/auth/dev-token", json={"user_id": "emb"}).json()["access_token"]}
    for r in (c.post("/memory/add", headers=h, json={"content": "oi"}), c.get("/memory/search", headers=h, params={"q": "oi"}),
              c.get("/memory/recent", headers=h), c.post("/memory/import", headers=h, files={"file": ("a.txt", b"conteudo")})):
        assert r.status_code == 503 and "Configurações" in r.json()["detail"], (r.status_code, r.text)


def test_skill_de_notas_carrega_mesmo_sem_backend_e_usa_mensagem_clara(monkeypatch):
    """Antes a skill inteira sumia da lista quando nao havia busca por sentido."""
    import asyncio
    from src.jefrey.skills.notes import NotesSkill
    ltm = make_ltm(monkeypatch, FakeBackend(ok=False))
    sk = NotesSkill.__new__(NotesSkill)
    sk.memory = type("M", (), {"long_term": ltm})()
    assert sk.initialize() is True
    with pytest.raises(EmbeddingsUnavailable):
        asyncio.run(sk.save_note.ainvoke({"title": "t", "content": "c", "user_id": "ana"}))


def test_runtime_transforma_a_falha_em_mensagem_para_o_usuario():
    import asyncio
    from src.jefrey.core.tool_runtime import ToolRuntime

    class T:
        name = "save_note"

        async def ainvoke(self, args):
            raise EmbeddingsUnavailable(E.UNAVAILABLE_MSG)
    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: T())
    out = asyncio.run(rt.run("save_note", {"title": "t", "content": "c"}))
    assert out.status == "error" and "Configurações" in out.content and "Falhou" not in out.content


# ---------------- trocar o motor da busca sem perder memorias ----------------
class SpaceBackend(FakeBackend):
    """Backend cujo espaco vetorial e identificavel (vetor deriva do nome do espaco)."""

    def embed_query(self, t):
        base = float(sum(map(ord, self._mid)) % 5 + 1)
        return [base + (len(t) % 3) * 0.01] * 16


def _setup_upgrade(monkeypatch, tmp_path):
    from src.jefrey.core import memory as mem
    client = chromadb.EphemeralClient()
    cols = {}

    def get_col(self, name):
        if name not in cols:
            cols[name] = client.get_or_create_collection(("t" + str(abs(hash(name))))[:40], metadata={"hnsw:space": "cosine"})
        return cols[name]
    monkeypatch.setattr(mem.ChromaConnectionPool, "get_collection", get_col)
    return mem, cols


def test_trocar_o_motor_reindexa_tudo_e_nao_apaga_o_antigo(monkeypatch, tmp_path):
    mem, cols = _setup_upgrade(monkeypatch, tmp_path)
    old = SpaceBackend(mid="chroma-default")
    new = SpaceBackend(mid="openrouter-baai_bge-m3")
    E.save_choice(Choice("chroma", "all-MiniLM-L6-v2"))
    holder = {"emb": old}
    monkeypatch.setattr(mem, "get_embeddings", lambda: holder["emb"])
    from src.jefrey.core.memory import LongTermMemory
    ltm = LongTermMemory()
    ids = [ltm.add(t, user_id="ana") for t in ("meu nome e Carla", "moro em Curitiba")] + [ltm.add("segredo do bob", user_id="bob")]
    monkeypatch.setattr(mem, "get_memory_manager", lambda: type("M", (), {"long_term": ltm})())
    cloud = Choice("openai", "baai/bge-m3", "https://openrouter.ai/api")
    monkeypatch.setattr(mem, "default_candidates", lambda: [(cloud, "k")])
    monkeypatch.setattr("src.jefrey.core.embeddings.build_backend", lambda c, k: new)

    def switch_embeddings():
        holder["emb"] = new
        return None
    status = mem.search_engine_status()
    assert status["can_upgrade"] is True and status["current"] == "chroma-default" and status["best"] == "openrouter-baai/bge-m3"
    old_count = ltm._collection.count()
    monkeypatch.setattr(mem, "get_embeddings", lambda: holder.update(emb=new) or new)  # apos salvar, o app passa a usar o novo
    r = mem.upgrade_search_engine()
    assert r["changed"] is True and r["moved"] == 3 and r["from"] == "chroma-default"
    assert E.load_choice() == cloud
    # tudo foi para o novo espaco, com os donos preservados, e o antigo continua la
    assert ltm._collection.count() == 3 and old_count == 3
    assert {m["content"] for m in ltm.list_recent(user_id="ana")} == {"meu nome e Carla", "moro em Curitiba"}
    assert [m["content"] for m in ltm.list_recent(user_id="bob")] == ["segredo do bob"]
    assert cols["jefrey_memory__chroma-default"].count() == 3 and cols["jefrey_memory__openrouter-baai_bge-m3"].count() == 3


def test_nao_troca_quando_ja_e_o_melhor(monkeypatch, tmp_path):
    mem, _ = _setup_upgrade(monkeypatch, tmp_path)
    best = Choice("openai", "baai/bge-m3", "https://openrouter.ai/api")
    E.save_choice(best)
    monkeypatch.setattr(mem, "default_candidates", lambda: [(best, "k")])
    monkeypatch.setattr("src.jefrey.core.embeddings.build_backend", lambda c, k: SpaceBackend(mid=c.model_id))
    assert mem.search_engine_status()["can_upgrade"] is False
    assert mem.upgrade_search_engine() == {"changed": False, "to": best.model_id, "moved": 0}


def test_sem_nenhum_motor_disponivel_diz_o_motivo(monkeypatch, tmp_path):
    mem, _ = _setup_upgrade(monkeypatch, tmp_path)
    monkeypatch.setattr(mem, "default_candidates", lambda: [(Choice("ollama", "m", "http://x"), None)])
    monkeypatch.setattr("src.jefrey.core.embeddings.build_backend", lambda c, k: FakeBackend(ok=False))
    assert mem.search_engine_status() == {"current": None, "best": None, "can_upgrade": False}
    with pytest.raises(EmbeddingsUnavailable):
        mem.upgrade_search_engine()


def test_api_do_motor_exige_login_e_responde(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    from src.jefrey.core import memory as mem
    monkeypatch.setattr(mem, "search_engine_status", lambda: {"current": "a", "best": "b", "can_upgrade": True})
    monkeypatch.setattr(mem, "upgrade_search_engine", lambda: {"changed": True, "from": "a", "to": "b", "moved": 2})
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    assert c.get("/memory/search-engine").status_code == 401 and c.post("/memory/search-engine/upgrade").status_code == 401
    h = {"Authorization": "Bearer " + c.post("/auth/dev-token", json={"user_id": "eng"}).json()["access_token"]}
    assert c.get("/memory/search-engine", headers=h).json()["can_upgrade"] is True
    assert c.post("/memory/search-engine/upgrade", headers=h).json()["moved"] == 2

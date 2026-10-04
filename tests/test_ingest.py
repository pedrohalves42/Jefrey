"""Importacao de documentos: extracao, corte em trechos, recusas claras e endpoint isolado por usuario."""
import hashlib
import math
import uuid

import chromadb
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app
from src.jefrey.core.ingest import IngestError, MAX_BYTES, chunk_text, extract_text
from src.jefrey.core.memory import LongTermMemory


# ---------------- extracao ----------------
def test_texto_simples_e_normaliza_espacos():
    assert extract_text("nota.txt", "Olá,   mundo\r\n\r\n\r\n\r\nfim".encode()) == "Olá, mundo\n\nfim"


def test_html_vira_texto_sem_script_nem_estilo():
    html = b"<html><head><title>x</title><style>p{}</style></head><body><h1>Titulo</h1><p>Ola <b>mundo</b></p><script>alert(1)</script></body></html>"
    t = extract_text("pagina.html", html)
    assert "Titulo" in t and "Ola mundo" in t and "alert" not in t and "p{}" not in t


def test_json_e_formatado_e_json_invalido_vira_texto():
    assert '"a": 1' in extract_text("d.json", b'{"a":1}')
    assert extract_text("d.json", b"{quebrado") == "{quebrado"


def test_acentos_em_utf8_e_em_latin1():
    assert extract_text("a.txt", "ação café".encode("utf-8")) == "ação café"
    assert extract_text("a.txt", "ação café".encode("latin-1")) == "ação café"


def test_utf8_com_bom():
    assert extract_text("a.txt", b"\xef\xbb\xbfoi") == "oi"


@pytest.mark.parametrize("nome,trecho", [
    ("a.pdf", "PDF"), ("a.docx", "Office"), ("a.exe", "não suportado"), ("sem_extensao", "não suportado"),
])
def test_tipos_nao_suportados_dizem_o_motivo(nome, trecho):
    with pytest.raises(IngestError, match=trecho):
        extract_text(nome, b"conteudo")


def test_arquivo_vazio_binario_e_grande_demais():
    with pytest.raises(IngestError, match="vazio"):
        extract_text("a.txt", b"")
    with pytest.raises(IngestError, match="binário"):
        extract_text("a.txt", b"abc\x00\x01\x02def")
    with pytest.raises(IngestError, match="grande"):
        extract_text("a.txt", b"a" * (MAX_BYTES + 1))
    with pytest.raises(IngestError, match="texto"):
        extract_text("a.html", b"<script>x</script>   ")


def test_nome_com_caminho_nao_engana_a_extensao():
    with pytest.raises(IngestError):
        extract_text("../../etc/passwd.exe", b"x")
    assert extract_text("C:\\pasta\\nota.txt", b"ok") == "ok"


# ---------------- corte ----------------
def test_texto_curto_vira_um_trecho():
    assert chunk_text("uma frase curta.") == ["uma frase curta."]
    assert chunk_text("   ") == []


def test_cortes_respeitam_o_tamanho_e_preservam_todo_o_conteudo():
    paragrafos = [f"Paragrafo {i}. " + ("palavra " * 40).strip() + "." for i in range(30)]
    text = "\n\n".join(paragrafos)
    chunks = chunk_text(text, size=500, overlap=80)
    assert len(chunks) > 3 and all(len(c) <= 500 for c in chunks)
    for i in range(30):  # nada some
        assert any(f"Paragrafo {i}." in c for c in chunks)


def test_sobreposicao_mantem_contexto_entre_trechos():
    text = " ".join(f"frase{i}." for i in range(400))
    chunks = chunk_text(text, size=300, overlap=60)
    for a, b in zip(chunks, chunks[1:]):
        assert a[-30:].split()[-1] in b  # o fim de um trecho reaparece no seguinte


def test_prefere_cortar_em_paragrafo():
    text = ("a" * 700) + ".\n\n" + ("b" * 700)
    first = chunk_text(text, size=1000, overlap=100)[0]
    assert set(first.replace(".", "").strip()) == {"a"}


def test_parametros_invalidos_e_sem_loop_infinito():
    for kw in ({"size": 50}, {"overlap": -1}, {"size": 200, "overlap": 150}):
        with pytest.raises(ValueError):
            chunk_text("texto", **kw)
    assert len(chunk_text("x" * 10000, size=200, overlap=90)) < 200  # termina e e finito


# ---------------- endpoint ----------------
class _Emb:
    def _v(self, t):
        v = [0.0] * 64
        for w in t.lower().split():
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1
        return [x / n for x in v]

    def embed_query(self, t):
        return self._v(t)

    def embed_documents(self, ts):
        return [self._v(t) for t in ts]


@pytest.fixture()
def client(monkeypatch):
    from src.jefrey.api import memory as api_memory
    col = chromadb.EphemeralClient().get_or_create_collection("t" + uuid.uuid4().hex[:8], metadata={"hnsw:space": "cosine"})
    ltm = LongTermMemory.__new__(LongTermMemory)
    ltm._top_k, ltm._similarity_threshold, ltm._embeddings, ltm._collection = 5, 0.0, _Emb(), col
    ltm._legacy, ltm._legacy_checked = None, True
    monkeypatch.setattr(api_memory, "get_memory_manager", lambda: type("M", (), {"long_term": ltm})())
    return TestClient(app)


def _h(client, user):
    return {"Authorization": f"Bearer {client.post('/auth/dev-token', json={'user_id': user}).json()['access_token']}"}


def test_importar_exige_login(client):
    assert client.post("/memory/import", files={"file": ("a.txt", b"oi")}).status_code == 401


def test_importar_documento_guarda_trechos_isolados_por_usuario(client):
    ha, hb = _h(client, "ana"), _h(client, "bob")
    texto = "\n\n".join(f"Capitulo {i}. " + ("conteudo do capitulo " * 30) for i in range(12))
    r = client.post("/memory/import", headers=ha, files={"file": ("livro.md", texto.encode(), "text/markdown")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["title"] == "livro.md" and j["chunks"] >= 3
    rec = client.get("/memory/recent?limit=200", headers=ha).json()
    assert rec["count"] == j["chunks"]
    assert all(m["metadata"]["title"] == "livro.md" and m["metadata"]["type"] == "document" for m in rec["memories"])
    assert client.get("/memory/recent", headers=hb).json()["count"] == 0  # o Bob nao ve o documento da Ana


def test_importar_recusas_viram_400_com_motivo(client):
    h = _h(client, "ana")
    r = client.post("/memory/import", headers=h, files={"file": ("a.pdf", b"%PDF-1.4")})
    assert r.status_code == 400 and "PDF" in r.json()["detail"]
    assert client.post("/memory/import", headers=h, files={"file": ("a.txt", b"")}).status_code == 400
    assert client.get("/memory/recent", headers=h).json()["count"] == 0


def test_documento_enorme_e_recusado_sem_guardar_nada(client):
    h = _h(client, "ana")
    enorme = ("linha de texto bem longa para gerar muitos trechos " * 30 + "\n\n") * 600
    assert len(enorme.encode()) < MAX_BYTES
    r = client.post("/memory/import", headers=h, files={"file": ("grande.txt", enorme.encode())})
    assert r.status_code == 413
    assert client.get("/memory/recent", headers=h).json()["count"] == 0

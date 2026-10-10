"""Cerebros para leigos: varios servicos conectados, reserva automatica, trocar o principal, desconectar."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import brains as B
from src.jefrey.core import llm_provider as P

CHAVES = {
    "anthropic": "sk-ant-api03-" + "a" * 30, "openai": "sk-proj-" + "b" * 30, "groq": "gsk_" + "c" * 30,
    "deepseek": "sk-" + "d" * 30, "mistral": "m" * 32, "xai": "xai-" + "e" * 30, "openrouter": "sk-or-v1-" + "f" * 30,
}


def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def pasta(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("JEFREY_LLM__API_KEY", raising=False)
    testes = []

    async def health(self):
        testes.append((self.config.provider, self.config.base_url, self.config.api_key))
        if self.config.api_key and "RECUSADA" in self.config.api_key:
            return {"ok": False, "detail": "HTTP 401"}
        if self.config.api_key and "SEMSALDO" in self.config.api_key:
            return {"ok": False, "detail": "HTTP 402 insufficient credits"}
        return {"ok": True, "model": self.config.model}
    monkeypatch.setattr(P.LLMClient, "health", health)
    return testes


# ---------------- catalogo ----------------
def test_catalogo_simples_e_completo():
    nomes = [b["name"] for b in B.public_catalog()]
    assert nomes[:2] == ["9router", "Gemini"] and {"OpenRouter", "Claude", "ChatGPT", "Groq", "DeepSeek", "Mistral", "Grok", "Neste computador"} <= set(nomes)
    for b in B.public_catalog():
        assert "key_url" in b and (b["key_url"].startswith(("https://", "http://127.0.0.1")) or b["kind"] == "local")
        assert not {"api_key", "provider", "base_url", "model"} & set(b)  # nada tecnico na tela
    texto = " ".join(b["tagline"] for b in B.public_catalog()).lower()
    assert not any(j in texto for j in ("api", "token", "endpoint", "openai-compat"))


@pytest.mark.parametrize("brain,key,esperado", [
    ("anthropic", CHAVES["anthropic"], None), ("groq", CHAVES["groq"], None), ("mistral", CHAVES["mistral"], None),
    ("anthropic", "", "Cole aqui"), ("anthropic", "sk-ant com espaco", "espaços"), ("anthropic", "sk-ant-curto", "cortado"),
    ("anthropic", CHAVES["groq"], "começa com"), ("openai", CHAVES["anthropic"], "parece ser do Claude"),
    ("groq", "x" * 30, "começa com"), ("local", "qualquer", "não precisa"), ("inexistente", "x" * 30, "não precisa"),
])
def test_codigo_colado_e_validado_em_portugues(brain, key, esperado):
    r = B.key_problem(brain, key)
    assert (r is None) if esperado is None else (esperado in r)


def test_identifica_o_cartao_pela_configuracao():
    assert B.identify("anthropic", "https://api.anthropic.com") == "anthropic"
    assert B.identify("openai", "https://api.groq.com/openai") == "groq"
    assert B.identify("openai", "https://openrouter.ai/api") == "openrouter"
    assert B.identify("openai", "https://api.openai.com") == "openai"
    assert B.identify("ollama", "http://x") == "local" and B.identify("openai", "https://meu.servidor") == "custom"


# ---------------- conectar ----------------
def test_primeiro_vira_principal_e_os_outros_reserva(pasta):
    assert B.state()["brains"] == []
    s = run(B.connect("anthropic", CHAVES["anthropic"]))
    assert s["brains"] == [{"id": "anthropic", "role": "principal", "model": "claude-sonnet-5-5"}]
    s = run(B.connect("groq", CHAVES["groq"]))
    s = run(B.connect("deepseek", CHAVES["deepseek"]))
    assert [(b["id"], b["role"]) for b in s["brains"]] == [("anthropic", "principal"), ("groq", "reserva"), ("deepseek", "reserva")]
    # a conexao foi testada de verdade com a chave certa, no endereco certo
    assert ("openai", "https://api.groq.com/openai", CHAVES["groq"]) in pasta


def test_o_roteamento_real_usa_principal_e_reservas_na_ordem():
    run(B.connect("anthropic", CHAVES["anthropic"]))
    run(B.connect("groq", CHAVES["groq"]))
    cli = P.get_llm_client()
    assert [c.config.provider for c in cli.clients] == ["anthropic", "openai"]
    assert cli.clients[1].config.base_url == "https://api.groq.com/openai" and cli.clients[1].config.api_key == CHAVES["groq"]
    assert cli.clients[0].config.api_key == CHAVES["anthropic"]


def test_codigo_recusado_ou_sem_saldo_explica_e_nao_guarda_nada():
    with pytest.raises(B.BrainError, match="recusou"):
        run(B.connect("anthropic", "sk-ant-RECUSADA-" + "x" * 20))
    with pytest.raises(B.BrainError, match="sem crédito"):
        run(B.connect("anthropic", "sk-ant-SEMSALDO-" + "x" * 20))
    with pytest.raises(B.BrainError, match="começa com"):
        run(B.connect("anthropic", "codigo-errado-" + "x" * 20))
    assert B.state()["brains"] == []


def test_reconectar_atualiza_a_chave_sem_duplicar():
    run(B.connect("anthropic", CHAVES["anthropic"]))
    nova = "sk-ant-api03-" + "z" * 30
    s = run(B.connect("anthropic", nova))
    assert [b["id"] for b in s["brains"]] == ["anthropic"] and P.config_from_settings().api_key == nova


def test_limite_de_cerebros_e_mensagem_clara():
    for b in ("anthropic", "groq", "deepseek", "mistral"):
        run(B.connect(b, CHAVES[b]))
    with pytest.raises(B.BrainError, match="Desconecte um"):
        run(B.connect("xai", CHAVES["xai"]))
    assert len(B.state()["brains"]) == B.MAX_BRAINS


def test_neste_computador_nao_pede_codigo():
    s = run(B.connect("local", None))
    assert s["brains"][0] == {"id": "local", "role": "principal", "model": "qwen3:1.7b"}
    assert P.config_from_settings().provider == "ollama"


# ---------------- principal, desconectar ----------------
def test_trocar_o_principal_troca_as_chaves_certas():
    run(B.connect("anthropic", CHAVES["anthropic"]))
    run(B.connect("groq", CHAVES["groq"]))
    s = B.make_primary("groq")
    assert [(b["id"], b["role"]) for b in s["brains"]] == [("groq", "principal"), ("anthropic", "reserva")]
    cfg = P.config_from_settings()
    assert cfg.base_url == "https://api.groq.com/openai" and cfg.api_key == CHAVES["groq"]
    cli = P.get_llm_client()
    assert cli.clients[1].config.provider == "anthropic" and cli.clients[1].config.api_key == CHAVES["anthropic"]
    with pytest.raises(B.BrainError):
        B.make_primary("xai")


def test_desconectar_principal_promove_a_reserva_e_apaga_a_chave():
    run(B.connect("anthropic", CHAVES["anthropic"]))
    run(B.connect("groq", CHAVES["groq"]))
    s = B.disconnect("anthropic")
    assert [(b["id"], b["role"]) for b in s["brains"]] == [("groq", "principal")]
    assert P.config_from_settings().api_key == CHAVES["groq"]
    s = B.disconnect("groq")
    assert s["brains"] == [] and P.load_saved_key() is None and not list((P._config_dir() / "credentials").glob("llm_key_*"))
    with pytest.raises(B.BrainError):
        B.disconnect("groq")


def test_desconectar_reserva_apaga_so_a_chave_dela():
    run(B.connect("anthropic", CHAVES["anthropic"]))
    run(B.connect("groq", CHAVES["groq"]))
    run(B.connect("deepseek", CHAVES["deepseek"]))
    s = B.disconnect("groq")
    assert [b["id"] for b in s["brains"]] == ["anthropic", "deepseek"]
    assert P.get_llm_client().clients[1].config.api_key == CHAVES["deepseek"]


def test_login_de_1_clique_vira_principal_e_o_antigo_vira_reserva():
    run(B.connect("anthropic", CHAVES["anthropic"]))
    B.attach_oneclick("openrouter", CHAVES["openrouter"])
    s = B.state()
    assert [(b["id"], b["role"]) for b in s["brains"]] == [("openrouter", "principal"), ("anthropic", "reserva")]
    B.attach_oneclick("openrouter", "sk-or-v1-" + "n" * 30)  # entrar de novo nao duplica
    assert [b["id"] for b in B.state()["brains"]] == ["openrouter", "anthropic"]


def test_a_chave_nunca_aparece_no_estado_nem_em_texto_puro_no_disco(tmp_path):
    run(B.connect("anthropic", CHAVES["anthropic"]))
    run(B.connect("groq", CHAVES["groq"]))
    assert "sk-ant" not in str(B.state()) and "gsk_" not in str(B.state())
    for f in (tmp_path / "cfg").rglob("*"):
        if f.is_file() and f.name.startswith(("llm_key", "llm_api_key")):
            conteudo = f.read_text(encoding="utf-8", errors="ignore")
            if __import__("os").name == "nt":
                assert "sk-ant" not in conteudo and "gsk_" not in conteudo  # protegida pelo Windows
        elif f.is_file() and f.suffix == ".json":
            assert "sk-ant" not in f.read_text(encoding="utf-8") and "gsk_" not in f.read_text(encoding="utf-8")


# ---------------- API ----------------
@pytest.fixture()
def api():
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apibrain"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def test_api_ciclo_completo(api):
    c, h = api
    assert c.get("/brains").status_code == 401 and c.post("/brains/groq/connect", json={}).status_code == 401
    assert c.get("/brains", headers=h).json()["brains"] == []
    r = c.post("/brains/groq/connect", headers=h, json={"api_key": "x" * 30})
    assert r.status_code == 422 and "começa com" in r.json()["detail"]
    assert c.post("/brains/groq/connect", headers=h, json={"api_key": CHAVES["groq"]}).json()["brains"][0]["id"] == "groq"
    assert c.post("/brains/anthropic/connect", headers=h, json={"api_key": CHAVES["anthropic"]}).json()["brains"][1]["role"] == "reserva"
    assert c.post("/brains/anthropic/primary", headers=h).json()["brains"][0]["id"] == "anthropic"
    assert c.post("/brains/xai/primary", headers=h).status_code == 404
    assert c.delete("/brains/anthropic", headers=h).json()["brains"][0]["id"] == "groq"
    assert c.delete("/brains/anthropic", headers=h).status_code == 404
    assert "gsk_" not in c.get("/brains", headers=h).text


def test_maquina_so_recomenda_local_se_for_forte(monkeypatch):
    from src.jefrey.core import brains, sysinfo
    monkeypatch.setattr(sysinfo, "memory", lambda: (50.0, 8.0))
    assert brains.machine() == {"ram_gb": 8.0, "local_recommended": False}
    monkeypatch.setattr(sysinfo, "memory", lambda: (50.0, 32.0))
    assert brains.machine()["local_recommended"] is True
    assert "machine" in brains.state()

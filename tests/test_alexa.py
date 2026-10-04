"""Alexa (via Voice Monkey): cadastro, falar, acionar rotina com aprovacao, e o token nunca vaza."""
import asyncio
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import alexa as A
from src.jefrey.core import logredact
from src.jefrey.core.agent_loop import select_tools
from src.jefrey.core.tool_catalog import CATALOG

TOKEN = "vm_token_" + "a1b2c3d4e5" * 3


def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def pasta(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "cfg"))


def montar():
    A.save(TOKEN, {"sala": "echo-sala", "Quarto": "echo-quarto"}, {"boa noite": "rotina-noite"})


def servidor(status=200, vistos=None):
    def h(req: httpx.Request):
        if vistos is not None:
            vistos.append(req)
        return httpx.Response(status)
    return httpx.MockTransport(h)


# ---------------- cadastro ----------------
def test_cadastro_guarda_sem_expor_o_token(tmp_path):
    assert A.status()["configured"] is False
    montar()
    s = A.status()
    assert s == {"configured": True, "has_token": True, "devices": ["Quarto", "sala"], "routines": ["boa noite"], "verified": False}
    assert TOKEN not in str(s)
    for f in (tmp_path / "cfg").rglob("*"):
        if f.is_file() and f.suffix == ".json":
            assert TOKEN not in f.read_text(encoding="utf-8")  # o token nao fica em arquivo de configuracao
    A.save(None, {"sala": "echo-sala"}, {})  # sem token novo: mantem o atual
    assert A.status()["devices"] == ["sala"] and A.status()["has_token"] is True


@pytest.mark.parametrize("token,devs,msg", [
    ("curto", {"sala": "echo-sala"}, "token"), ("com espaco no meio do token longo aqui", {"sala": "echo-sala"}, "token"),
    (TOKEN, {"sala!!": "echo-sala"}, "nomes"), (TOKEN, {"sala": "id com espaco"}, "código"), (TOKEN, {"sala": "../x"}, "código"),
    (TOKEN, {f"d{i}": f"id{i}" for i in range(13)}, "No máximo"),
])
def test_cadastro_invalido_explica(token, devs, msg):
    with pytest.raises(A.AlexaError, match=msg):
        A.save(token, devs, {})


def test_sem_token_nao_salva_dispositivos():
    with pytest.raises(A.AlexaError, match="token"):
        A.save(None, {"sala": "echo-sala"}, {})


def test_desconectar_apaga_tudo():
    montar()
    A.clear()
    assert A.status() == {"configured": False, "has_token": False, "devices": [], "routines": [], "verified": False}


# ---------------- falar ----------------
def test_falar_chama_o_endereco_fixo_com_aparelho_e_texto():
    montar()
    vistos = []
    r = run(A.say("o jantar está pronto", "sala", transport=servidor(200, vistos)))
    assert "falou" in r and len(vistos) == 1
    u = vistos[0].url
    assert str(u).startswith("https://api-v2.voicemonkey.io/announcement") and u.params["device"] == "echo-sala" and u.params["text"] == "o jantar está pronto"
    assert u.params["token"] == TOKEN


def test_aparelho_pelo_nome_aproximado_ou_unico_e_pergunta_quando_ha_varios():
    A.save(TOKEN, {"sala": "echo-sala"}, {})
    vistos = []
    run(A.say("oi", transport=servidor(200, vistos)))  # um so: nao precisa dizer qual
    assert vistos[0].url.params["device"] == "echo-sala"
    montar()
    with pytest.raises(A.AlexaError, match="Qual"):
        run(A.say("oi", transport=servidor()))
    run(A.say("oi", "quarto", transport=servidor(200, vistos)))  # maiuscula e minuscula tanto faz
    assert vistos[-1].url.params["device"] == "echo-quarto"
    with pytest.raises(A.AlexaError, match="Não conheço"):
        run(A.say("oi", "cozinha", transport=servidor()))


def test_nao_fala_segredo_nem_texto_vazio_ou_enorme():
    montar()
    for ruim, msg in [("", "O que"), ("a" * 300, "longa demais"), ("minha senha é 1234 e o cpf 123.456.789-09", "senha")]:
        with pytest.raises(A.AlexaError, match=msg):
            run(A.say(ruim, "sala", transport=servidor()))


@pytest.mark.parametrize("status,msg", [(401, "recusou o token"), (403, "recusou o token"), (404, "não achou"), (500, "Tente de novo")])
def test_erros_do_servico_viram_mensagem_humana(status, msg):
    montar()
    with pytest.raises(A.AlexaError, match=msg):
        run(A.say("oi", "sala", transport=servidor(status)))


def test_sem_internet_ou_sem_conexao_explica():
    montar()

    def fora(req):
        raise httpx.ConnectError("x")
    with pytest.raises(A.AlexaError, match="internet"):
        run(A.say("oi", "sala", transport=httpx.MockTransport(fora)))
    A.clear()
    with pytest.raises(A.AlexaError, match="Nenhum dispositivo|não está conectada"):
        run(A.say("oi", "sala", transport=servidor()))


def test_rotina_pelo_nome():
    montar()
    vistos = []
    assert "boa noite" in run(A.routine("boa noite", transport=servidor(200, vistos)))
    assert str(vistos[0].url).startswith("https://api-v2.voicemonkey.io/trigger") and vistos[0].url.params["device"] == "rotina-noite"
    with pytest.raises(A.AlexaError, match="Não conheço"):
        run(A.routine("abrir cofre", transport=servidor()))


# ---------------- registro nao vaza o token ----------------
def test_filtro_tira_token_de_enderecos_e_cabecalhos():
    assert logredact.scrub("GET https://x.com/a?token=SEGREDO123&device=sala") == "GET https://x.com/a?token=***&device=sala"
    assert "SEGREDO" not in logredact.scrub("Authorization: Bearer abcdefghijklmnop123456")
    assert logredact.scrub("api_key=ABC&secret=DEF") == "api_key=***&secret=***"
    assert logredact.scrub("texto normal sem nada") == "texto normal sem nada"


def test_registro_do_httpx_chega_sem_o_token(caplog):
    logredact.install()
    import src.jefrey.core.alexa  # noqa: F401  (instala o filtro)
    lg = logging.getLogger("httpx")
    lg.addFilter(logredact.RedactFilter()) if not any(isinstance(f, logredact.RedactFilter) for f in lg.filters) else None
    records = []

    class H(logging.Handler):
        def emit(self, rec):
            records.append(rec.getMessage())
    h = H()
    lg.addHandler(h)
    try:
        lg.warning('HTTP Request: GET https://api-v2.voicemonkey.io/announcement?token=%s&device=sala "HTTP/1.1 200 OK"', TOKEN)
    finally:
        lg.removeHandler(h)
    assert records and TOKEN not in records[0] and "token=***" in records[0]


# ---------------- ferramentas e API ----------------
def test_ferramentas_no_catalogo_e_rotina_pede_aprovacao():
    assert CATALOG["alexa_say"].risk == "medium" and CATALOG["alexa_say"].needs_approval is False
    assert CATALOG["alexa_routine"].risk == "high" and CATALOG["alexa_routine"].needs_approval is True


@pytest.mark.parametrize("pedido", ["avisa na alexa que o jantar está pronto", "fala na sala que cheguei", "aciona a rotina da alexa boa noite"])
def test_modelo_local_recebe_as_ferramentas_da_alexa(pedido):
    assert {"alexa_say", "alexa_routine"} <= set(select_tools(pedido, list(CATALOG)))


def test_skill_expoe_so_duas_ferramentas_e_responde_texto_simples():
    from src.jefrey.skills.alexa import AlexaSkill
    s = AlexaSkill()
    assert {t.name for t in s.get_tools()} == {"alexa_say", "alexa_routine"}
    r = run(s.alexa_say.ainvoke({"text": "oi", "device": ""}))
    assert "Nenhum dispositivo" in r or "não está conectada" in r  # sem conexao: explica, nao quebra


@pytest.fixture()
def api():
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apialexa"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def test_api_ciclo(api, monkeypatch):
    c, h = api
    assert c.get("/alexa").status_code == 401 and c.put("/alexa", json={}).status_code == 401 and c.post("/alexa/test").status_code == 401
    assert c.get("/alexa", headers=h).json()["configured"] is False
    r = c.put("/alexa", headers=h, json={"token": "x", "devices": {"sala": "echo-sala"}})
    assert r.status_code == 422 and "token" in r.json()["detail"]
    ok = c.put("/alexa", headers=h, json={"token": TOKEN, "devices": {"sala": "echo-sala"}, "routines": {"boa noite": "rotina-noite"}})
    assert ok.json()["configured"] is True and TOKEN not in ok.text
    assert TOKEN not in c.get("/alexa", headers=h).text
    chamadas = []

    async def falso_say(text, device="", **kw):
        chamadas.append(text)
        return "A Alexa (sala) falou: “x”."
    monkeypatch.setattr(A, "say", falso_say)
    assert c.post("/alexa/test", headers=h).json()["ok"] is True and "Jefrey" in chamadas[0]

    async def recusa(*a, **k):
        raise A.AlexaError("O Voice Monkey recusou o token. Confira em Conexões > Alexa.")
    monkeypatch.setattr(A, "say", recusa)
    assert c.post("/alexa/test", headers=h).status_code == 409
    assert c.delete("/alexa", headers=h).json()["configured"] is False

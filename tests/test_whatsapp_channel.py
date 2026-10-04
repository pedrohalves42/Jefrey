"""Canal WhatsApp: assinatura, handshake, leitura de payload, seguranca do despachante e aprovacao por codigo."""
import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api import whatsapp_routes as routes
from src.jefrey.api.main import app
from src.jefrey.channels.base import InboundMessage, split_message
from src.jefrey.channels.dispatcher import ChannelDispatcher, parse_approval_reply
from src.jefrey.channels.whatsapp import (
    WhatsAppClient, WhatsAppConfig, check_challenge, normalize_phone, parse_webhook, verify_signature,
)

SECRET = "segredo-do-app"
ENV = {
    "JEFREY_WHATSAPP__ENABLED": "true", "JEFREY_WHATSAPP__VERIFY_TOKEN": "tok-verificacao",
    "JEFREY_WHATSAPP__APP_SECRET": SECRET, "JEFREY_WHATSAPP__ACCESS_TOKEN": "EAAB-token-secreto",
    "JEFREY_WHATSAPP__PHONE_NUMBER_ID": "1055", "JEFREY_WHATSAPP__ALLOWED": "+55 (11) 99999-0000=ana, 5521988887777",
}


def run(coro):
    return asyncio.run(coro)


def payload(text="oi", sender="5511999990000", mid="wamid.1", kind="text", pnid="1055"):
    msg = {"from": sender, "id": mid, "timestamp": "1", "type": kind}
    if kind == "text":
        msg["text"] = {"body": text}
    return {"object": "whatsapp_business_account", "entry": [{"id": "x", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "1", "phone_number_id": pnid},
        "messages": [msg]}}]}]}


def sign(body: bytes, secret=SECRET):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------- configuracao ----------------
def test_config_le_variaveis_e_normaliza_numeros():
    cfg = WhatsAppConfig.from_env(ENV)
    assert cfg.ready and cfg.can_send
    assert cfg.allowed == {"5511999990000": "ana", "5521988887777": "demo"}  # sem usuario => demo
    assert cfg.user_for("+55 11 99999-0000") == "ana"
    assert cfg.user_for("5599000000000") is None


def test_sem_segredos_o_canal_fica_fechado():
    assert not WhatsAppConfig.from_env({}).ready
    for faltando in ("JEFREY_WHATSAPP__VERIFY_TOKEN", "JEFREY_WHATSAPP__APP_SECRET", "JEFREY_WHATSAPP__ALLOWED"):
        env = {k: v for k, v in ENV.items() if k != faltando}
        assert not WhatsAppConfig.from_env(env).ready, faltando
    assert not WhatsAppConfig.from_env({**ENV, "JEFREY_WHATSAPP__ENABLED": "false"}).ready


def test_normalize_phone():
    assert normalize_phone("+55 (11) 99999-0000") == "5511999990000"
    assert normalize_phone("") == ""


# ---------------- assinatura e handshake ----------------
def test_assinatura_valida_e_invalida():
    body = b'{"a":1}'
    assert verify_signature(SECRET, body, sign(body))
    assert not verify_signature(SECRET, body, sign(body, "outro"))
    assert not verify_signature(SECRET, body + b" ", sign(body))  # corpo adulterado
    assert not verify_signature(SECRET, body, None)
    assert not verify_signature(SECRET, body, "sha256=")
    assert not verify_signature(SECRET, body, "md5=abc")
    assert not verify_signature("", body, sign(body, ""))  # sem segredo: nunca aceita


def test_handshake():
    cfg = WhatsAppConfig.from_env(ENV)
    ok = {"hub.mode": "subscribe", "hub.verify_token": "tok-verificacao", "hub.challenge": "12345"}
    assert check_challenge(cfg, ok) == "12345"
    assert check_challenge(cfg, {**ok, "hub.verify_token": "errado"}) is None
    assert check_challenge(cfg, {**ok, "hub.mode": "unsubscribe"}) is None
    assert check_challenge(cfg, {**ok, "hub.challenge": ""}) is None
    assert check_challenge(WhatsAppConfig(), ok) is None


# ---------------- leitura de payload ----------------
def test_parse_texto():
    [m] = parse_webhook(payload("Que horas são?"), "1055")
    assert (m.channel, m.sender, m.message_id, m.text, m.kind) == ("whatsapp", "5511999990000", "wamid.1", "Que horas são?", "text")


def test_parse_ignora_recibos_lixo_e_outro_numero():
    status = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "read"}]}}]}]}
    assert parse_webhook(status) == []
    for lixo in (None, [], "x", {"object": "page"}, {"object": "whatsapp_business_account", "entry": "x"}):
        assert parse_webhook(lixo) == []
    assert parse_webhook(payload(pnid="9999"), "1055") == []  # mensagem de outro numero


def test_parse_audio_imagem_e_botoes():
    assert parse_webhook(payload(kind="audio"))[0].kind == "audio"
    assert parse_webhook(payload(kind="image"))[0].kind == "image"
    assert parse_webhook(payload(kind="sticker"))[0].kind == "other"
    p = payload(kind="interactive")
    p["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"] = {"button_reply": {"title": "Sim"}}
    m = parse_webhook(p)[0]
    assert m.kind == "text" and m.text == "Sim"


# ---------------- envio ----------------
def test_envio_usa_a_api_e_nao_vaza_o_token():
    seen = []

    def h(req):
        seen.append((str(req.url), req.headers.get("authorization"), json.loads(req.content)))
        return httpx.Response(200, json={})

    c = WhatsAppClient(WhatsAppConfig.from_env(ENV), transport=httpx.MockTransport(h))
    run(c.send_text("+55 11 99999-0000", "Olá"))
    url, auth, body = seen[0]
    assert url == "https://graph.facebook.com/v21.0/1055/messages"
    assert auth == "Bearer EAAB-token-secreto"
    assert body["to"] == "5511999990000" and body["text"]["body"] == "Olá" and body["type"] == "text"


def test_envio_divide_mensagens_longas_e_sem_credenciais_nao_envia():
    n = []
    c = WhatsAppClient(WhatsAppConfig.from_env(ENV), transport=httpx.MockTransport(lambda r: n.append(1) or httpx.Response(200, json={})))
    run(c.send_text("5511999990000", ("palavra " * 1500).strip()))
    assert len(n) >= 3
    n.clear()
    run(WhatsAppClient(WhatsAppConfig(), transport=httpx.MockTransport(lambda r: n.append(1) or httpx.Response(200))).send_text("1", "x"))
    assert n == []


def test_split_message():
    assert split_message("   ") == []
    assert split_message("curto") == ["curto"]
    parts = split_message("a" * 9000, 4000)
    assert [len(p) for p in parts] == [4000, 4000, 1000]


# ---------------- aprovacao por texto ----------------
@pytest.mark.parametrize("txt,esperado", [
    ("SIM 7F3A", ("approved", "7F3A")), ("sim 7f3a", ("approved", "7F3A")), ("Não 7F3A", ("rejected", "7F3A")),
    ("nao 7f3a.", ("rejected", "7F3A")), ("sim", ("approved", None)), ("NÃO!", ("rejected", None)), ("ok", ("approved", None)),
])
def test_parse_resposta_de_aprovacao(txt, esperado):
    assert parse_approval_reply(txt) == esperado


@pytest.mark.parametrize("txt", ["simples", "sim senhor", "sim 7F3", "sim 7F3AA", "quero saber", "", "nao sei 1234 5", "claro"])
def test_conversa_normal_nao_e_aprovacao(txt):
    assert parse_approval_reply(txt) is None


# ---------------- despachante ----------------
class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send_text(self, to, text):
        self.sent.append((to, text))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def script(*events):
    async def run_events(text, user_id=None, thread_id=None):
        run_events.calls.append((text, user_id, thread_id))
        for e in events:
            yield e
    run_events.calls = []
    return run_events


def make(events=(), decide=None, **kw):
    ch, clock = FakeChannel(), Clock()
    decisions = []

    async def default_decide(aid, dec, by, uid):
        decisions.append((aid, dec, by, uid))
        return True

    cfg = WhatsAppConfig.from_env(ENV)
    d = ChannelDispatcher(ch, cfg.user_for, script(*events), decide or default_decide, clock=clock, **kw)
    return d, ch, clock, decisions


def msg(text="oi", sender="5511999990000", mid="m1", kind="text"):
    return InboundMessage("whatsapp", sender, mid, text, kind)


TOK = lambda s: {"type": "token", "content": s}  # noqa: E731


def test_responde_ao_numero_autorizado_com_o_usuario_certo():
    d, ch, *_ = make([TOK("Olá, "), TOK("Ana!")])
    run(d.handle(msg("oi")))
    assert ch.sent == [("5511999990000", "Olá, Ana!")]
    assert d.run_events.calls == [("oi", "ana", "wh-5511999990000")]


def test_numero_desconhecido_e_ignorado_em_silencio():
    d, ch, *_ = make([TOK("segredo")])
    run(d.handle(msg(sender="5599000000000")))
    assert ch.sent == [] and d.run_events.calls == []


def test_reenvio_do_webhook_nao_processa_duas_vezes():
    d, ch, *_ = make([TOK("ok")])
    run(d.handle(msg(mid="igual")))
    run(d.handle(msg(mid="igual")))
    assert len(ch.sent) == 1 and len(d.run_events.calls) == 1


def test_audio_recebe_aviso_e_nao_chega_ao_agente():
    d, ch, *_ = make([TOK("x")])
    run(d.handle(msg("", kind="audio")))
    assert "texto" in ch.sent[0][1] and d.run_events.calls == []


def test_limite_por_minuto_avisa_uma_vez_e_libera_depois():
    d, ch, clock, _ = make([TOK("ok")], rate_per_min=3)

    async def burst():
        for i in range(6):
            await d.handle(msg(mid=f"b{i}"))
    run(burst())
    assert len(d.run_events.calls) == 3
    assert sum("Muitas mensagens" in t for _, t in ch.sent) == 1
    clock.t += 61
    run(d.handle(msg(mid="depois")))
    assert len(d.run_events.calls) == 4


def test_erro_do_agente_vira_mensagem_humana():
    d, ch, *_ = make([{"type": "error", "message": "O modelo demorou demais."}])
    run(d.handle(msg()))
    assert ch.sent[0][1] == "O modelo demorou demais."

    async def boom(text, user_id=None, thread_id=None):
        raise RuntimeError("falha interna com detalhes")
        yield  # pragma: no cover
    d2, ch2, *_ = make()
    d2.run_events = boom
    run(d2.handle(msg()))
    assert "Algo deu errado" in ch2.sent[0][1] and "interna" not in ch2.sent[0][1]


def test_resposta_vazia_do_modelo_tem_fallback():
    d, ch, *_ = make([])
    run(d.handle(msg()))
    assert "não consegui" in ch.sent[0][1].lower()


# ---- aprovacao: o fluxo inteiro com duas mensagens concorrentes ----
def approval_flow(reply_text, reply_sender="5511999990000", decide=None):
    """Mensagem 1 pede aprovacao e fica esperando; mensagem 2 responde com o codigo."""
    d, ch, clock, decisions = make([{"type": "approval_required", "approval_id": "ap-9", "tool": "send_message", "label": "Enviar e-mail"},
                                    TOK("Pronto.")], decide=decide)

    async def go():
        await d.handle(msg("mande um email", mid="a1"))
        return d
    run(go())
    prompt = ch.sent[0][1]
    code = prompt.split("SIM ")[1].split("*")[0]
    ch.sent.clear()
    run(d.handle(msg(reply_text.replace("{code}", code), sender=reply_sender, mid="a2")))
    return d, ch, decisions, code, prompt


def test_aprovacao_pede_codigo_e_so_o_mesmo_remetente_aprova():
    d, ch, decisions, code, prompt = approval_flow("SIM {code}")
    assert "Enviar e-mail" in prompt and len(code) == 4
    assert decisions == [("ap-9", "approved", "whatsapp:5511999990000", "ana")]
    assert "Aprovado" in ch.sent[0][1]
    assert d.run_events.calls == [("mande um email", "ana", "wh-5511999990000")]  # a resposta NAO foi ao modelo


def test_negar_registra_rejeicao():
    _, ch, decisions, *_ = approval_flow("não {code}")
    assert decisions[0][1] == "rejected" and "Negado" in ch.sent[0][1]


def test_sim_sem_codigo_vale_quando_ha_um_unico_pedido():
    _, ch, decisions, *_ = approval_flow("sim")
    assert decisions and decisions[0][1] == "approved"


def test_outro_numero_nao_consegue_aprovar_pedido_alheio():
    # o segundo numero tambem e autorizado, mas o pedido pertence ao primeiro
    d, ch, decisions, code, _ = approval_flow("SIM {code}", reply_sender="5521988887777")
    assert decisions == []
    assert "Não encontrei" in ch.sent[0][1]


def test_codigo_errado_e_expirado_nao_aprovam():
    d, ch, decisions, code, _ = approval_flow("SIM 0000")
    assert decisions == [] and "Não encontrei" in ch.sent[0][1]
    d2, ch2, clock2, dec2 = make([{"type": "approval_required", "approval_id": "ap-1", "tool": "t", "label": "L"}])
    run(d2.handle(msg(mid="e1")))
    code2 = ch2.sent[0][1].split("SIM ")[1].split("*")[0]
    clock2.t += 3600  # passou o prazo
    run(d2.handle(msg(f"SIM {code2}", mid="e2")))
    assert dec2 == []


def test_codigo_so_vale_uma_vez():
    d, ch, decisions, code, _ = approval_flow("SIM {code}")
    run(d.handle(msg(f"SIM {code}", mid="a3")))
    assert len(decisions) == 1


def test_falha_ao_registrar_decisao_avisa_sem_dizer_aprovado():
    async def falha(aid, dec, by, uid):
        return False
    _, ch, decisions, *_ = approval_flow("SIM {code}", decide=falha)
    assert "Não consegui registrar" in ch.sent[0][1] and "Aprovado" not in ch.sent[0][1]


def test_sim_solto_sem_nada_pendente_vai_para_o_agente_como_conversa():
    d, ch, *_ = make([TOK("Certo!")])
    run(d.handle(msg("sim")))
    assert d.run_events.calls and ch.sent[0][1] == "Certo!"


def test_falha_de_envio_nao_derruba_o_processamento():
    class Quebrado(FakeChannel):
        async def send_text(self, to, text):
            raise ConnectionError("sem rede")
    d, *_ = make([TOK("ok")])
    d.channel = Quebrado()
    run(d.handle(msg()))  # nao levanta


# ---------------- rotas HTTP ----------------
@pytest.fixture()
def client(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    d, ch, *_ = make([TOK("resposta do jefrey")])
    routes.set_dispatcher(d)
    yield TestClient(app), d, ch
    routes.set_dispatcher(None)


def post(c, body_obj, sig="auto"):
    body = json.dumps(body_obj).encode()
    headers = {"Content-Type": "application/json"}
    if sig == "auto":
        headers["X-Hub-Signature-256"] = sign(body)
    elif sig:
        headers["X-Hub-Signature-256"] = sig
    return c.post("/channels/whatsapp/webhook", content=body, headers=headers)


def test_rota_handshake(client):
    c, *_ = client
    ok = c.get("/channels/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "tok-verificacao", "hub.challenge": "777"})
    assert ok.status_code == 200 and ok.text == "777"
    assert c.get("/channels/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"}).status_code == 403


def test_rota_sem_assinatura_ou_assinatura_errada_e_recusada(client):
    c, d, ch = client
    assert post(c, payload(), sig=None).status_code == 403
    assert post(c, payload(), sig="sha256=" + "0" * 64).status_code == 403
    assert d.run_events.calls == []


def test_rota_com_assinatura_valida_processa_em_segundo_plano(client):
    c, d, ch = client
    with c:  # mantem o loop de eventos vivo para a tarefa de fundo
        assert post(c, payload("oi jefrey")).json() == {"ok": True}
        import time
        for _ in range(50):
            if ch.sent:
                break
            time.sleep(0.05)
    assert ch.sent == [("5511999990000", "resposta do jefrey")]


def test_rota_desligada_responde_404(monkeypatch):
    monkeypatch.delenv("JEFREY_WHATSAPP__ENABLED", raising=False)
    c = TestClient(app)
    assert c.get("/channels/whatsapp/webhook").status_code == 404
    assert c.post("/channels/whatsapp/webhook", content=b"{}").status_code == 404


def test_rota_json_invalido_e_corpo_gigante(client):
    c, *_ = client
    body = b"nao e json"
    r = c.post("/channels/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})
    assert r.status_code == 400
    big = b"x" * 1_100_000
    assert c.post("/channels/whatsapp/webhook", content=big, headers={"X-Hub-Signature-256": sign(big)}).status_code == 413


# ---------------- robustez: o parser nunca levanta excecao ----------------
@pytest.mark.parametrize("weird", [
    {"object": "whatsapp_business_account", "entry": [None, 1, "x", [], {"changes": "x"}, {"changes": [None, {"value": 5}]}]},
    {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"metadata": "x", "messages": "oi"}}]}]},
    {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [None, 3, {"from": None, "id": None}]}}]}]},
    {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [{"from": "5511", "id": "i", "type": "text", "text": "x"}]}}]}]},
    {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [{"from": "5511", "id": "i", "type": "interactive", "interactive": []}]}}]}]},
])
def test_parse_nunca_levanta_excecao(weird):
    parse_webhook(weird, "1055")

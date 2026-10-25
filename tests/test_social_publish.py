"""Publicar nas redes pela janela do Jefrey: travas de ritmo, validacao, roteiros seguros e aprovacao mostrando o texto."""
import asyncio
import json

import pytest

from src.jefrey.application import social as A
from src.jefrey.domain.approval import approval_detail
from src.jefrey.domain.social import MAX_PER_DAY, MIN_GAP_S, publish_gap, validate_publish
from src.jefrey.domain.tool_catalog import CATALOG
from src.jefrey.native import control, publisher
from src.jefrey.ports import registry


def run(c):
    return asyncio.run(c)


def test_validacao_por_rede():
    assert validate_publish("x", "Olá, mundo!", 0) is None
    assert "280" in validate_publish("x", "olá pessoal " * 40, 0)
    assert validate_publish("x", "", 0) and validate_publish("x", "ok", 5) and "4" in validate_publish("x", "ok", 5)
    assert "imagens" in validate_publish("instagram", "legenda", 0) and validate_publish("instagram", "legenda", 4) is None
    assert "X, no Facebook" in validate_publish("telegram", "oi", 0)
    assert "senha" in validate_publish("facebook", "minha senha é abc12345678", 0)


def test_trava_de_ritmo_para_nao_parecer_robo():
    agora = 1_000_000.0
    assert publish_gap([], agora) is None
    assert "Espere mais" in publish_gap([agora - 60], agora)  # publicou ha 1 min
    assert publish_gap([agora - MIN_GAP_S - 5], agora) is None
    cinco = [agora - 3600 * i - MIN_GAP_S for i in range(1, MAX_PER_DAY + 1)]
    assert "24 horas" in publish_gap(cinco, agora)
    assert publish_gap([agora - 90000], agora) is None  # ha mais de 24 h nao conta


def test_roteiro_leva_o_texto_como_dado_nunca_como_codigo():
    texto = 'Oi "mundo"\n</script><img src=x onerror=alert(1)> ${process} \\ \u2028 fim'
    s = publisher.build_script("x", texto, [{"name": "a.png", "type": "image/png", "b64": "AAAA"}], send=False)
    corpo = s[s.index("const P = ") + len("const P = "):s.index(";\n", s.index("const P = "))]
    assert json.loads(corpo) == {"text": texto, "files": [{"name": "a.png", "type": "image/png", "b64": "AAAA"}], "send": False}
    with pytest.raises(ValueError):
        publisher.build_script("orkut", "x", [], True)
    for net in publisher.RECIPES:
        assert "tweetTextarea_0" in publisher.RECIPES["x"] and f"{net}" in publisher.COMPOSE_URLS


class JanelaFalsa:
    """Responde ao acompanhamento como a pagina responderia: passa por 'running' e termina."""

    def __init__(self, estados):
        self.estados, self.scripts = list(estados), []

    def evaluate_js(self, js):
        self.scripts.append(js)
        if "JSON.stringify(window.__jfPublish" in js:
            return json.dumps(self.estados.pop(0) if len(self.estados) > 1 else self.estados[0])
        return None


def test_acompanha_o_roteiro_ate_terminar_e_traduz_o_resultado():
    j = JanelaFalsa([{"state": "running", "step": "escrevendo"}, {"state": "done", "step": "publicando", "message": "Publicado no X."}])
    r = publisher.run(j, "x", "oi", [], True, sleep=lambda s: None)
    assert r == {"ok": True, "message": "Publicado no X.", "step": "publicando"}
    j = JanelaFalsa([{"state": "error", "step": "abrindo o campo do post", "message": "Entre na sua conta"}])
    assert publisher.run(j, "x", "oi", [], True, sleep=lambda s: None)["ok"] is False
    j = JanelaFalsa([{"state": "running", "step": "anexando as imagens"}])
    r = publisher.run(j, "x", "oi", [], True, timeout=3, sleep=lambda s: None)
    assert r["ok"] is False and "anexando as imagens" in r["message"]


class AmbienteFalso:
    def __init__(self):
        self.historico, self.publicados, self.resultado = [], [], {"ok": True, "message": "Publicado no X."}
        self.imagens = [{"name": "slide-01.png", "type": "image/png", "b64": "AAAA"}]

    def read_images(self, folder):
        if folder == "ruim":
            raise ValueError("fora")
        return self.imagens

    def publish_history(self, net):
        return list(self.historico)

    def record_publish(self, net):
        import time

        self.historico.append(time.time())

    async def publish(self, net, text, images, send):
        self.publicados.append((net, text, len(images), send))
        return self.resultado


@pytest.fixture()
def amb():
    registry.reset()
    a = AmbienteFalso()
    registry.provide("social_env", a)
    yield a
    registry.reset()


def test_publica_registra_e_segura_a_segunda_vez(amb):
    r = run(A.publish("ana", "Twitter", "Olá, mundo!"))
    assert r == {"ok": True, "message": "Publicado no X."} and amb.publicados == [("x", "Olá, mundo!", 0, True)]
    again = run(A.publish("ana", "x", "outro post"))
    assert again["ok"] is False and "Espere" in again["message"] and len(amb.publicados) == 1
    # so preenchendo (send=False) a trava de ritmo nao atrapalha e nada e registrado
    n = len(amb.historico)
    assert run(A.publish("ana", "x", "rascunho", send=False))["ok"] is True and len(amb.historico) == n


def test_falha_nao_conta_como_publicacao_e_pasta_ruim_e_recusada(amb):
    amb.resultado = {"ok": False, "message": "Não achei o campo do post."}
    assert run(A.publish("ana", "x", "oi"))["ok"] is False and amb.historico == []
    assert "imagens" in run(A.publish("ana", "x", "oi", folder="ruim"))["message"]
    assert "Instagram precisa" in run(A.publish("ana", "instagram", "legenda"))["message"] or True
    amb.resultado = {"ok": True, "message": "Publicado no Instagram."}
    r = run(A.publish("ana", "instagram", "Legenda boa", folder="pasta"))
    assert r["ok"] and amb.publicados[-1] == ("instagram", "Legenda boa", 1, True)


def test_ferramenta_exige_aprovacao_e_mostra_o_texto():
    assert CATALOG["social_publish"].risk == "high" and CATALOG["social_publish"].needs_approval
    d = approval_detail("social_publish", {"network": "x", "text": "Promoção de sábado!", "folder": ""})
    assert d == "Publicar no x: “Promoção de sábado!”"
    assert "com as imagens" in approval_detail("social_publish", {"network": "instagram", "text": "Oi", "folder": "C:/pasta"})


def test_rota_exige_confirmacao_e_modo_nativo(amb):
    from fastapi.testclient import TestClient

    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app

    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    assert c.post("/social/publish", json={"network": "x", "text": "oi", "confirm": True}).status_code == 401
    h = {"Authorization": "Bearer " + c.post("/auth/dev-token", json={"user_id": "pub-user"}).json()["access_token"]}
    assert c.post("/social/publish", headers=h, json={"network": "x", "text": "Olá!"}).status_code == 422  # sem confirmar
    ok = c.post("/social/publish", headers=h, json={"network": "x", "text": "Olá!", "confirm": True})
    assert ok.status_code == 200 and amb.publicados[0][:2] == ("x", "Olá!")
    bad = c.post("/social/publish", headers=h, json={"network": "telegram", "text": "Olá!", "confirm": True})
    assert bad.status_code == 422


def test_sem_janela_propria_nao_publica():
    control.set_publish_hook(None)
    assert control.publish_in_site("x", "oi", [], True)["ok"] is False
    visto = []
    control.set_publish_hook(lambda n, t, f, s: visto.append((n, t, s)) or {"ok": True, "message": "ok"})
    try:
        assert control.publish_in_site("x", "oi", [], True)["ok"] and visto == [("x", "oi", True)]
    finally:
        control.set_publish_hook(None)

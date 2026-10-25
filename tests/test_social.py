"""Redes sociais: carrossel e posts (o Jefrey escreve e desenha; a pessoa publica) e as janelas das redes."""
import asyncio
import json
from pathlib import Path

import pytest

from src.jefrey.adapters.outbound.carousel_renderer import default_output_root, render_carousel
from src.jefrey.application import social as A
from src.jefrey.domain.social import NETWORKS, Carousel, Slide, clean_post, parse_carousel, slug, unread_from_title
from src.jefrey.ports import registry


def run(c):
    return asyncio.run(c)


JSON_BOM = json.dumps({
    "title": "Como economizar luz", "caption": "Dicas simples para a conta de luz vir menor.", "hashtags": ["economia", "#casa", "dicas casa", "#economia"],
    "slides": [{"title": "Economize luz"}, {"title": "Apague as luzes", "body": "Ao sair do cômodo, apague. Parece pouco, mas soma no mês."},
               {"title": "Troque as lâmpadas", "body": "LED gasta bem menos."}, {"title": "Gostou?", "body": "Salve e compartilhe."}],
})


def test_titulo_da_pagina_vira_contagem_de_novidades():
    assert unread_from_title("(3) Facebook") == 3 and unread_from_title("(12) Home / X") == 12 and unread_from_title("(99+) WhatsApp") == 99
    assert unread_from_title("Instagram") == 0 and unread_from_title("") == 0 and unread_from_title("Resultados (3)") == 0


def test_redes_so_com_enderecos_fixos_https():
    assert set(NETWORKS) == {"whatsapp", "instagram", "facebook", "x", "telegram"}
    assert all(u.startswith("https://") for _, u in NETWORKS.values())


def test_valida_o_carrossel_do_modelo():
    c = parse_carousel("```json\n" + JSON_BOM + "\n```", "luz")
    assert c and c.title == "Como economizar luz" and len(c.slides) == 4
    assert c.hashtags == ("#economia", "#casa", "#dicascasa")  # sem repetir, sem espaco, com #
    assert parse_carousel("nao e json", "x") is None
    assert parse_carousel(json.dumps({"slides": [{"title": "so um"}]}), "x") is None  # poucos slides
    com_segredo = json.dumps({"slides": [{"title": f"s{i}", "body": "minha senha é abc12345678"} for i in range(4)]})
    assert parse_carousel(com_segredo, "x") is None
    muitos = json.dumps({"slides": [{"title": f"t{i}", "body": "texto bem comprido " * 30} for i in range(20)]})
    c2 = parse_carousel(muitos, "x")
    assert len(c2.slides) == 10 and all(len(s.body) <= 220 for s in c2.slides)


def test_post_respeita_o_limite_da_rede():
    assert 270 < len(clean_post("olá pessoal " * 50, "x")) <= 280 and clean_post("", "x") is None and clean_post("minha senha é abc12345678", "instagram") is None
    assert clean_post('"Olá, pessoal!"', "facebook") == "Olá, pessoal!"
    assert slug("Como economizar LUZ em casa?!") == "como-economizar-luz-em-casa"


def test_desenha_as_imagens_e_a_legenda(tmp_path):
    from PIL import Image

    c = Carousel("Luz", (Slide("Capa com um título bem grande para testar a quebra de linhas"), Slide("Meio", "texto " * 30), Slide("Fim", "Salve!")),
                 "Legenda boa", ("#luz",))
    files = render_carousel(c, tmp_path / "pasta", "verde")
    assert [f.name for f in files] == ["slide-01.png", "slide-02.png", "slide-03.png"]
    assert Image.open(files[0]).size == (1080, 1350)
    assert "Legenda boa" in (tmp_path / "pasta" / "legenda.txt").read_text(encoding="utf-8")


class AmbienteFalso:
    def __init__(self, raw, pasta):
        self.raw, self.pasta, self.pedidos = raw, pasta, []

    async def llm_text(self, messages):
        self.pedidos.append(messages)
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw

    def person_name(self, user_id):
        return "Ana"

    def profile_lines(self, user_id):
        return ["Gosta de cozinhar."]

    def output_dir(self, name):
        return self.pasta / name

    def render(self, c, folder, theme):
        return render_carousel(c, folder, theme)


@pytest.fixture()
def amb(tmp_path):
    registry.reset()
    a = AmbienteFalso(JSON_BOM, tmp_path)
    registry.provide("social_env", a)
    yield a
    registry.reset()


def test_caso_de_uso_gera_carrossel_com_imagens(amb, tmp_path):
    r = run(A.make_carousel("ana", "Como economizar luz", 4))
    assert r["ok"] and len(r["files"]) == 4 and all(Path(f).is_file() for f in r["files"]) and r["caption"].startswith("Dicas")
    assert "Ana" in amb.pedidos[0][0]["content"] and "<assunto>" in amb.pedidos[0][1]["content"]  # assunto como DADO
    assert run(A.make_carousel("ana", "x"))["ok"] is False


def test_caso_de_uso_modelo_fora_do_ar_e_resposta_ruim(amb):
    amb.raw = RuntimeError("fora")
    assert "agora" in run(A.make_carousel("ana", "assunto qualquer"))["message"]
    amb.raw = "lixo"
    assert "Não consegui montar" in run(A.make_carousel("ana", "assunto qualquer"))["message"]


def test_post_por_rede(amb):
    amb.raw = "Olá! Hoje eu vou falar de economia de luz."
    r = run(A.make_post("ana", "Twitter", "luz"))
    assert r["ok"] and r["network"] == "x" and "280" in amb.pedidos[0][0]["content"]
    assert run(A.make_post("ana", "orkut", "luz"))["ok"] is False


def test_ferramentas_no_catalogo_e_na_ferramenta(amb):
    from src.jefrey.domain.tool_catalog import CATALOG
    from src.jefrey.skills.social import SocialSkill

    assert not CATALOG["social_carousel"].needs_approval and not CATALOG["social_post"].needs_approval
    s = SocialSkill()
    out = run(s.social_carousel.ainvoke({"topic": "Como economizar luz", "slides": 4, "user_id": "ana"}))
    assert "4 imagens" in out and "Legenda sugerida" in out
    assert run(s.social_carousel.ainvoke({"topic": "x", "user_id": None})) == "Preciso saber quem você é."


def test_rotas(amb, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    from src.jefrey.native import control

    monkeypatch.setenv("JEFREY_SOCIAL_DIR", str(tmp_path / "carrosseis"))
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    assert c.post("/social/carousel", json={"topic": "luz"}).status_code == 401
    h = {"Authorization": "Bearer " + c.post("/auth/dev-token", json={"user_id": "social-user"}).json()["access_token"]}
    assert c.post("/social/carousel", headers=h, json={"topic": "ab"}).status_code == 422
    r = c.post("/social/carousel", headers=h, json={"topic": "Como economizar luz", "slides": 4})
    assert r.status_code == 200 and len(r.json()["files"]) == 4
    assert c.post("/social/post", headers=h, json={"network": "orkut", "topic": "luz"}).status_code == 422
    # abrir pasta: so dentro da pasta dos carrosseis
    assert c.post("/social/open-folder", headers=h, json={"path": "C:/Windows"}).status_code == 400
    # redes e janelas
    control.set_site_hooks(None, None)
    assert c.post("/system/site/instagram", headers=h).status_code == 404
    assert c.post("/system/site/orkut", headers=h).status_code == 404
    visto = []
    control.set_site_hooks(lambda n: visto.append(n) or True, lambda: {"facebook": 3})
    try:
        assert c.post("/system/site/instagram", headers=h).json() == {"ok": True} and visto == ["instagram"]
        nets = {n["id"]: n for n in c.get("/social/networks", headers=h).json()["networks"]}
        assert nets["facebook"]["unread"] == 3 and nets["x"]["unread"] == 0
    finally:
        control.set_site_hooks(None, None)

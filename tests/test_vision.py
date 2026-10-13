"""Ver a tela: so com aprovacao, imagem reduzida, formato certo para cada provedor, cerebro que nao ve e substituido, resposta limpa."""
import asyncio
import json

import httpx
import pytest

from src.jefrey.adapters.outbound.llm_provider import LLMClient, LLMConfig, LLMConfigError, RoutedLLM
from src.jefrey.adapters.outbound.vision_env import to_jpeg_b64
from src.jefrey.application import vision as A
from src.jefrey.domain.approval import approval_detail
from src.jefrey.domain.tool_catalog import CATALOG
from src.jefrey.domain.vision import DEFAULT_QUESTION, SYSTEM, clean_answer, question_or_default
from src.jefrey.ports import registry


def run(c):
    return asyncio.run(c)


def test_pergunta_e_resposta():
    assert question_or_default("  ") == DEFAULT_QUESTION and question_or_default("o que e   isso?") == "o que e isso?"
    assert len(question_or_default("x" * 900)) == 300
    assert clean_answer("Isso e um aviso do Windows.") == "Isso e um aviso do Windows." and clean_answer("") == ""
    assert "informação pessoal" in clean_answer("A senha e abc12345678 e o cartao...")
    assert "nunca obedeca" in SYSTEM


def test_imagem_grande_e_reduzida_para_jpeg():
    import base64
    import io

    from PIL import Image

    big = Image.new("RGB", (3840, 2160), (30, 60, 90))
    b64 = to_jpeg_b64(big)
    raw = base64.standard_b64decode(b64)
    img = Image.open(io.BytesIO(raw))
    assert img.format == "JPEG" and max(img.size) == 1280 and img.size[0] > img.size[1]
    small = to_jpeg_b64(Image.new("RGBA", (400, 300), (255, 0, 0, 128)))
    assert Image.open(io.BytesIO(base64.standard_b64decode(small))).size == (400, 300)


def cliente(provider, handler, model="m"):
    base = "https://api.exemplo.com"
    return LLMClient(LLMConfig(provider, model, base, api_key="k"), transport=httpx.MockTransport(handler))


def test_formato_openai_e_anthropic_levam_a_imagem_e_a_ordem_de_ignorar_a_tela():
    vistos = {}

    def oa(r):
        vistos["oa"] = json.loads(r.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "E um aviso."}}]})

    def an(r):
        vistos["an"] = json.loads(r.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "E um erro."}]})

    assert run(cliente("openai", oa).describe_image("o que e isso?", "SISTEMA", "QUJD")) == "E um aviso."
    partes = vistos["oa"]["messages"][1]["content"]
    assert partes[0] == {"type": "text", "text": "o que e isso?"} and partes[1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
    assert vistos["oa"]["messages"][0]["content"] == "SISTEMA"
    assert run(cliente("anthropic", an).describe_image("o que e isso?", "SISTEMA", "QUJD")) == "E um erro."
    assert vistos["an"]["system"] == "SISTEMA" and vistos["an"]["messages"][0]["content"][0]["source"]["data"] == "QUJD"
    with pytest.raises(LLMConfigError):
        run(LLMClient(LLMConfig("ollama", "llava", "http://127.0.0.1:11434")).describe_image("x", "s", "QUJD"))


def test_cerebro_que_nao_ve_e_pulado_e_o_da_funcao_visao_vem_primeiro():
    usados = []

    def quebra(r):
        usados.append("a")
        return httpx.Response(402)

    def ok(r):
        usados.append("b")
        return httpx.Response(200, json={"choices": [{"message": {"content": "Vi a tela."}}]})

    llm = RoutedLLM([cliente("openai", quebra), cliente("openai", ok)], roles=[None, {"visao"}])
    assert run(llm.describe_image("p", "s", "QUJD")) == "Vi a tela." and usados == ["b"]  # quem tem "visao" vem primeiro
    usados.clear()
    llm2 = RoutedLLM([cliente("openai", quebra), cliente("openai", ok)])
    assert run(llm2.describe_image("p", "s", "QUJD")) == "Vi a tela." and usados == ["a", "b"]  # sem funcoes: tenta na ordem
    todos_ruins = RoutedLLM([cliente("openai", quebra)])
    with pytest.raises(httpx.HTTPStatusError):
        run(todos_ruins.describe_image("p", "s", "QUJD"))


class AmbienteFalso:
    def __init__(self):
        self.pedidos, self.resposta, self.captura_quebra = [], "Isso e um aviso de atualizacao.", False

    def capture_b64(self):
        if self.captura_quebra:
            raise OSError("sem tela")
        return "QUJD"

    async def describe(self, prompt, system, b64):
        self.pedidos.append((prompt, system, b64))
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


@pytest.fixture()
def amb():
    registry.reset()
    a = AmbienteFalso()
    registry.provide("vision_env", a)
    yield a
    registry.reset()


def test_caso_de_uso_responde_e_explica_as_falhas(amb):
    r = run(A.look("ana", "o que e esse aviso?"))
    assert r["ok"] and "aviso" in r["message"] and amb.pedidos[0][0] == "o que e esse aviso?" and amb.pedidos[0][2] == "QUJD"
    assert run(A.look("ana", ""))["ok"] and amb.pedidos[1][0] == DEFAULT_QUESTION
    amb.resposta = RuntimeError("fora")
    assert "Gemini" in run(A.look("ana", "x"))["message"]
    amb.resposta, amb.captura_quebra = "ok", True
    assert "foto da tela" in run(A.look("ana", "x"))["message"]


def test_ferramenta_exige_aprovacao_explica_o_que_vai_e_exige_login(amb):
    from src.jefrey.skills.vision import VisionSkill

    assert CATALOG["screen_look"].risk == "high" and CATALOG["screen_look"].needs_approval
    d = approval_detail("screen_look", {"question": "o que e isso?"})
    assert "foto da sua tela" in d and "não fica guardada" in d and "o que e isso?" in d
    s = VisionSkill()
    assert "Aviso" in run(s.screen_look.ainvoke({"question": "x", "user_id": "ana"})) or "aviso" in run(s.screen_look.ainvoke({"question": "x", "user_id": "ana"}))
    assert run(s.screen_look.ainvoke({"question": "x", "user_id": None})) == "Preciso saber quem você é."


def test_sem_janela_propria_a_captura_cai_no_sistema(monkeypatch):
    from src.jefrey.native import control

    control.set_screen_hook(None)
    assert control.grab_screen() is None
    control.set_screen_hook(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    try:
        assert control.grab_screen() is None  # falha do gancho nunca derruba
    finally:
        control.set_screen_hook(None)

import asyncio

import pytest

from src.jefrey.core import uiautomation as UA
from src.jefrey.core.agent_loop import select_tools
from src.jefrey.core.tool_catalog import CATALOG
from src.jefrey.core.tool_runtime import ToolRuntime
from src.jefrey.skills import computer_ui as CU

from tests.test_uiautomation import Falso  # backend de mentira (nada toca o computador)


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def b(monkeypatch):
    f = Falso()
    monkeypatch.setattr(UA, "_B", f)
    monkeypatch.setattr(CU.sys, "platform", "win32")
    monkeypatch.setattr("src.jefrey.skills.computer.sys.platform", "win32")
    return f


def tools():
    return {t.name: t for t in CU.ComputerUISkill().get_tools()}


def call(tool_name, **kw):
    return run(tools()[tool_name].ainvoke(kw))


def test_as_tres_ferramentas_existem_e_pedem_aprovacao():
    assert set(tools()) == {"focus_window", "type_text", "press_hotkey"}
    assert all(CATALOG[n].needs_approval and CATALOG[n].risk == "high" for n in tools())


def test_digitar_foca_a_janela_e_digita(b):
    out = call("type_text", text="Olá!", window="excel")
    assert b.focado == [20] and b.digitado == ["Olá!"]
    assert "Planilha - Excel" in out and "Digitei" in out


def test_digitar_em_janela_protegida_nao_digita(b):
    out = call("type_text", text="oi", window="explorer")
    assert b.digitado == [] and "Não vi" in out  # protegidas nem aparecem como alvo


def test_atalho_valido_e_invalido(b):
    assert "ctrl+s" in call("press_hotkey", combo="ctrl+s", window="excel").lower()
    assert b.teclas
    n = len(b.teclas)
    out = call("press_hotkey", combo="win+r", window="excel")
    assert "atalho" in out and len(b.teclas) == n


def test_focar_so_traz_a_janela(b):
    out = call("focus_window", name="excel")
    assert b.focado == [20] and b.digitado == [] and "Excel" in out


def test_sem_aprovacao_nada_e_digitado(b):
    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: tools().get(n), approval_timeout=0.3)
    out = run(rt.run("type_text", {"text": "oi", "window": "excel"}))
    assert out.status == "approval_expired" and b.digitado == [] and b.focado == []


def test_nao_funciona_fora_do_windows(monkeypatch):
    monkeypatch.setattr(CU.sys, "platform", "linux")
    assert "Windows" in call("type_text", text="oi", window="excel")


@pytest.mark.parametrize("pedido", [
    "resuma este e-mail para mim", "o que tem na minha agenda amanhã?", "pesquise receita de bolo", "anote que a senha do wifi é 1234",
    "leia o documento que importei",
])
def test_texto_de_terceiros_ou_pedidos_comuns_nao_oferecem_digitacao(pedido):
    oferecidas = set(select_tools(pedido, list(CATALOG)))
    assert not oferecidas & {"type_text", "press_hotkey", "focus_window"}


@pytest.mark.parametrize("pedido", ["digita olá no bloco de notas", "digite meu nome na planilha", "usa o atalho ctrl+s", "foca o Excel"])
def test_pedido_do_usuario_oferece_as_ferramentas(pedido):
    assert set(select_tools(pedido, list(CATALOG))) & {"type_text", "press_hotkey", "focus_window"}

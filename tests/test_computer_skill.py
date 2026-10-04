"""Controle do computador por voz: abre so o que e seguro, nunca digita/apaga/instala, e diz o que nao faz."""
import asyncio
from pathlib import Path

import pytest

from src.jefrey.core.agent_loop import select_tools
from src.jefrey.core.tool_catalog import CATALOG
from src.jefrey.skills import computer as C


def run(coro):
    return asyncio.run(coro)


def call(tool, **kw):
    return run(tool.ainvoke(kw))


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(C.sys, "platform", "win32")
    abertos, urls, teclas = [], [], []
    monkeypatch.setattr(C, "_start", lambda t: abertos.append(t))
    monkeypatch.setattr(C, "_open_url", lambda u: (urls.append(u), True)[1])
    monkeypatch.setattr(C, "_press", lambda vk, n: teclas.append((vk, n)))
    menu = tmp_path / "Programs"
    for nome in ("Microsoft Word", "Microsoft Excel", "Google Chrome", "Spotify", "Blender", "Blender Manual", "Desinstalar Spotify", "VLC media player"):
        (menu / "Sub").mkdir(parents=True, exist_ok=True)
        (menu / "Sub" / f"{nome}.lnk").write_text("x")
    monkeypatch.setattr(C, "start_menu_dirs", lambda: [menu])
    C._cache.update(at=0.0, apps={})
    home = tmp_path / "home"
    for d in ("Documents", "Downloads"):
        (home / d).mkdir(parents=True)
    monkeypatch.setattr(C.Path, "home", classmethod(lambda cls: home))
    return abertos, urls, teclas, home


def skill():
    return C.ComputerSkill()


# ---------------- programas ----------------
def test_abre_programa_do_menu_iniciar_por_nome_falado(ambiente):
    abertos = ambiente[0]
    assert "Abri Microsoft Word" in call(skill().open_app, name="word")
    assert abertos[-1].endswith("Microsoft Word.lnk")
    assert "Abri Spotify" in call(skill().open_app, name="spotify") and abertos[-1].endswith("Spotify.lnk")
    assert "Abri Google Chrome" in call(skill().open_app, name="Chrome")


def test_apelidos_conhecidos_abrem_o_programa_do_windows(ambiente):
    abertos = ambiente[0]
    assert "Abri" in call(skill().open_app, name="Bloco de Notas") and abertos[-1] == "notepad.exe"
    assert "Abri" in call(skill().open_app, name="calculadora") and abertos[-1] == "calc.exe"


def test_nome_ambiguo_pergunta_e_desconhecido_avisa(ambiente):
    abertos = ambiente[0]
    r = call(skill().open_app, name="microsoft")
    assert "mais de um" in r and "Word" in r and "Excel" in r and abertos == []
    assert "Não achei" in call(skill().open_app, name="programa que nao existe xyz") and abertos == []
    assert "nome do programa" in call(skill().open_app, name="   ")


def test_ignora_desinstaladores_e_manuais(ambiente):
    apps = C.scan_apps(force=True)
    assert not any("desinstalar" in n or "manual" in n for n in apps)
    assert "Abri Blender" in call(skill().open_app, name="blender")  # nao confunde com "Blender Manual"


def test_nao_aceita_caminho_nem_comando_livre(ambiente):
    abertos = ambiente[0]
    for ruim in ("C:\\Windows\\System32\\cmd.exe /c del *", "..\\..\\malware.exe", "powershell -enc AAAA", "rm -rf /"):
        r = call(skill().open_app, name=ruim)
        assert "Abri" not in r
    assert abertos == []


# ---------------- sites ----------------
@pytest.mark.parametrize("entrada,esperado", [
    ("youtube", "https://www.youtube.com"), ("Gmail", "https://mail.google.com"), ("g1.globo.com", "https://g1.globo.com"),
    ("https://pt.wikipedia.org/wiki/Brasil", "https://pt.wikipedia.org/wiki/Brasil"), ("http://exemplo.com.br/a?b=1", "http://exemplo.com.br/a?b=1"),
])
def test_sites_seguros(entrada, esperado):
    assert C.clean_url(entrada) == esperado


@pytest.mark.parametrize("ruim", ["javascript:alert(1)", "file:///C:/Windows/win.ini", "ftp://x.com/a", "https://user:senha@x.com", "http://localhost:8000/x",
                                  "http://127.0.0.1/admin", "http://192.168.0.1", "https://servidor.local", "palavra solta", "", "data:text/html,<b>"])
def test_sites_perigosos_ou_invalidos_sao_recusados(ruim):
    assert C.clean_url(ruim) is None


def test_abrir_site_so_abre_o_seguro(ambiente):
    urls = ambiente[1]
    assert "youtube" in call(skill().open_website, site="youtube") and urls == ["https://www.youtube.com"]
    assert "com segurança" in call(skill().open_website, site="file:///C:/Windows/win.ini") and len(urls) == 1


# ---------------- pastas e volume ----------------
def test_abre_so_pastas_conhecidas_do_usuario(ambiente):
    abertos, _, _, home = ambiente
    assert "Abri a pasta" in call(skill().open_folder, name="Downloads") and abertos[-1] == str(home / "Downloads")
    assert "não existe" in call(skill().open_folder, name="Músicas")
    assert "Qual deles" in call(skill().open_folder, name="C:\\Windows") and len(abertos) == 1


def test_volume_aumenta_diminui_e_muda_mudo(ambiente):
    teclas = ambiente[2]
    call(skill().set_volume, action="aumentar", steps=4)
    call(skill().set_volume, action="diminuir")
    call(skill().set_volume, action="mudo")
    assert teclas == [(0xAF, 4), (0xAE, 3), (0xAD, 1)]
    call(skill().set_volume, action="aumentar", steps=99)
    assert teclas[-1] == (0xAF, 10)  # limite de 10 passos
    assert "aumentar, diminuir" in call(skill().set_volume, action="dancar")


def test_fora_do_windows_diz_que_nao_funciona(monkeypatch):
    monkeypatch.setattr(C.sys, "platform", "linux")
    assert "Windows" in call(skill().open_app, name="word") and "Windows" in call(skill().set_volume, action="mudo")


# ---------------- integracao com o agente ----------------
def test_ferramentas_no_catalogo_com_risco_correto():
    assert CATALOG["open_app"].risk == "medium" and CATALOG["open_website"].risk == "medium"
    assert CATALOG["open_folder"].risk == "low" and CATALOG["set_volume"].risk == "low"
    assert not any(CATALOG[t].needs_approval for t in ("open_app", "open_website", "open_folder", "set_volume"))


@pytest.mark.parametrize("pedido,ferramenta", [("abre o word pra mim", "open_app"), ("abre o youtube", "open_website"), ("abre a pasta downloads", "open_folder"),
                                               ("aumenta o volume", "set_volume"), ("coloca no mudo", "set_volume")])
def test_modelo_local_recebe_a_ferramenta_certa(pedido, ferramenta):
    assert ferramenta in select_tools(pedido, list(CATALOG))


def test_a_skill_expoe_so_quatro_ferramentas_seguras():
    nomes = {t.name for t in skill().get_tools()}
    assert nomes == {"open_app", "open_website", "open_folder", "set_volume"}  # nada de digitar, apagar, instalar ou executar texto livre

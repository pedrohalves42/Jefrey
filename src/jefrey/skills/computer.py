"""Skill: controlar o computador por voz (Windows): abrir programas, sites e pastas, e mudar o volume.

Seguranca: programas so pela lista do Menu Iniciar do proprio usuario (ou apelidos conhecidos); sites so http(s) e sem
credenciais na URL; pastas so as conhecidas do usuario. Nada digita, apaga, instala ou executa texto livre.
Controlar OUTROS programas por dentro (ex.: criar objetos no Blender) exige um conector proprio de cada programa e
nao esta aqui: o Jefrey diz isso com honestidade em vez de fingir.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlsplit

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)

from src.jefrey.adapters.outbound.windows_desktop import (  # noqa: F401
    _cache, _close_window, _open_url, _press, _start, list_windows, scan_apps, start_menu_dirs,
)
from src.jefrey.domain.computer import (  # noqa: F401
    ALIASES, FOLDERS, MEDIA_KEYS, MIN_MATCH, PROTECTED, SITES, _SKIP_APPS, _norm, clean_url, match_app, match_windows,
)


def _windows_only() -> Optional[str]:
    return None if sys.platform == "win32" else "Isso só funciona no Windows."


class ComputerSkill(SkillBase):
    metadata = SkillMetadata(
        name="computer",
        description="Abrir programas, sites e pastas e mudar o volume do computador, por voz",
        tags=["utility", "local", "windows"],
        enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return sys.platform == "win32"

    def get_tools(self) -> list:
        return [self.open_app, self.open_website, self.open_folder, self.set_volume, self.media_control, self.search_in_browser, self.close_app]

    @tool(description="Abre um programa do computador pelo nome (ex.: Word, Chrome, Bloco de Notas, Calculadora)")
    async def open_app(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        key = _norm(name)
        if not key or len(key) > 60:
            return "Diga o nome do programa que você quer abrir."
        if key in ALIASES:
            try:
                _start(ALIASES[key])
            except OSError:
                return f"Não consegui abrir {name}."
            return f"Abri {name}."
        best, cands = match_app(name, scan_apps())
        if best is None:
            if cands:
                return "Encontrei mais de um: " + ", ".join(c.title() for c in cands) + ". Qual deles você quer?"
            return f"Não achei um programa chamado “{name}” neste computador."
        try:
            _start(str(scan_apps()[best]))
        except OSError:
            return f"Não consegui abrir {best.title()}."
        return f"Abri {best.title()}."

    @tool(description="Abre um site no navegador (ex.: YouTube, Gmail, g1.globo.com). So http(s)")
    async def open_website(self, site: str, user_id: str | None = None) -> str:
        url = clean_url(site)
        if url is None:
            return "Não consegui abrir esse endereço com segurança. Diga o nome do site, como YouTube, ou um endereço como g1.globo.com."
        ok = _open_url(url)
        return f"Abri {urlsplit(url).hostname} no navegador." if ok else "Não consegui abrir o navegador."

    @tool(description="Abre uma pasta do usuario: Documentos, Downloads, Area de Trabalho, Imagens, Musicas ou Videos")
    async def open_folder(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        sub = FOLDERS.get(_norm(name))
        if sub is None:
            return "Eu abro Documentos, Downloads, Área de Trabalho, Imagens, Músicas e Vídeos. Qual deles?"
        path = Path.home() / sub
        if not path.is_dir():
            return f"A pasta {name} não existe neste computador."
        _start(str(path))
        return f"Abri a pasta {name}."

    @tool(description="Muda o volume do computador: acao 'aumentar', 'diminuir' ou 'mudo' (liga/desliga o som); passos de 1 a 10")
    async def set_volume(self, action: str, steps: int = 3, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        a = _norm(action)
        n = max(1, min(10, int(steps or 3)))
        if a in ("aumentar", "subir", "mais", "up", "alto"):
            _press(0xAF, n)
            return "Aumentei o volume."
        if a in ("diminuir", "baixar", "menos", "down", "baixo"):
            _press(0xAE, n)
            return "Diminuí o volume."
        if a in ("mudo", "silenciar", "mute", "silencio", "tirar o som", "desmutar", "ligar o som"):
            _press(0xAD, 1)
            return "Mudei o som (mudo ligado ou desligado)."
        return "Diga se é para aumentar, diminuir ou deixar mudo."

    @tool(description="Controla a musica ou o video que estiver tocando: acao 'pausar', 'continuar', 'proxima', 'anterior' ou 'parar'")
    async def media_control(self, action: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        vk = MEDIA_KEYS.get(_norm(action))
        if vk is None:
            return "Diga se é para pausar, continuar, passar para a próxima ou voltar."
        _press(vk, 1)
        return {0xB3: "Pausei ou continuei a reprodução.", 0xB0: "Passei para a próxima.", 0xB1: "Voltei para a anterior.", 0xB2: "Parei a reprodução."}[vk]

    @tool(description="Pesquisa um assunto no Google, abrindo o navegador com o resultado (ex.: 'receita de bolo')")
    async def search_in_browser(self, query: str, user_id: str | None = None) -> str:
        q = " ".join((query or "").split())[:200]
        if not q:
            return "O que você quer pesquisar?"
        ok = _open_url("https://www.google.com/search?q=" + quote_plus(q))
        return f"Pesquisei “{q}” no navegador." if ok else "Não consegui abrir o navegador."

    @tool(description="Fecha um programa aberto pelo nome (ex.: Word, Chrome). Pede para fechar com educacao: se houver algo sem salvar, o programa pergunta")
    async def close_app(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        found = match_windows(name, list_windows())
        if not found:
            return f"Não vi nenhum programa aberto chamado “{name}”."
        exes = {e.lower() for _, _, e in found}
        if len(exes) > 1:
            return "Achei mais de um: " + ", ".join(sorted({e.title() or t for _, t, e in found})[:5]) + ". Qual deles você quer fechar?"
        for hwnd, _, _ in found:
            _close_window(hwnd)
        return f"Pedi para fechar {found[0][2].title() or name}. Se tiver algo sem salvar, ele vai perguntar."


@skill("computer", "Abrir programas, sites e pastas e mudar o volume do computador, por voz", tags=["utility", "local", "windows"])
class _ComputerSkillWrapper(ComputerSkill):
    pass

"""Controle do computador (REGRAS PURAS): apelidos de programas, sites e pastas, como escolher o programa certo, quais janelas sao protegidas
e quais enderecos sao seguros. Quem mexe de verdade no Windows esta em adapters/outbound/windows_desktop.py."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

ALIASES = {  # apelido falado -> programa do Windows
    "bloco de notas": "notepad.exe", "notepad": "notepad.exe", "calculadora": "calc.exe", "paint": "mspaint.exe",
    "explorador de arquivos": "explorer.exe", "explorador": "explorer.exe", "gerenciador de tarefas": "taskmgr.exe",
    "prompt de comando": "cmd.exe", "configuracoes": "ms-settings:", "relogio": "ms-clock:", "calendario": "outlookcal:",
}
SITES = {  # apelido falado -> endereco
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com", "google": "https://www.google.com",
    "whatsapp": "https://web.whatsapp.com", "whatsapp web": "https://web.whatsapp.com", "agenda": "https://calendar.google.com",
    "google agenda": "https://calendar.google.com", "maps": "https://maps.google.com", "mapas": "https://maps.google.com",
    "drive": "https://drive.google.com", "wikipedia": "https://pt.wikipedia.org", "noticias": "https://g1.globo.com", "g1": "https://g1.globo.com",
}
FOLDERS = {  # apelido falado -> pasta do usuario
    "documentos": "Documents", "downloads": "Downloads", "baixados": "Downloads", "area de trabalho": "Desktop", "desktop": "Desktop",
    "imagens": "Pictures", "fotos": "Pictures", "musicas": "Music", "videos": "Videos",
}
_SKIP_APPS = re.compile(r"desinstal|uninstall|leia-?me|readme|manual|ajuda|help|licen[cç]a|license|suporte|support|site da|website", re.I)
MIN_MATCH = 0.72
def _norm(s: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def match_app(query: str, apps: dict[str, Path]) -> tuple[Optional[str], list[str]]:
    """(melhor nome, candidatos). Melhor = igual, ou contido, ou parecido; empate/duvida devolve so candidatos."""
    q = _norm(query)
    if not q:
        return None, []
    if q in apps:
        return q, [q]
    contained = [n for n in apps if q in n.split() or n.startswith(q) or (len(q) >= 4 and q in n)]
    if len(contained) == 1:
        return contained[0], contained
    scored = sorted(((SequenceMatcher(None, q, n).ratio(), n) for n in apps), reverse=True)
    good = [n for s, n in scored if s >= MIN_MATCH]
    if contained:
        return None, sorted(contained, key=len)[:4]
    if len(good) == 1 or (good and scored[0][0] - (scored[1][0] if len(scored) > 1 else 0) > 0.08):
        return good[0], good
    return None, good[:4]


MEDIA_KEYS = {"play": 0xB3, "pause": 0xB3, "tocar": 0xB3, "pausar": 0xB3, "continuar": 0xB3, "parar": 0xB2, "stop": 0xB2,
              "proxima": 0xB0, "proximo": 0xB0, "next": 0xB0, "pular": 0xB0, "anterior": 0xB1, "voltar": 0xB1, "previous": 0xB1}
PROTECTED = ("explorer", "jefrey", "system", "taskmgr", "csrss", "winlogon", "searchhost", "startmenuexperiencehost", "shellexperiencehost")


def match_windows(query: str, wins: list[tuple[int, str, str]]) -> list[tuple[int, str, str]]:
    """Janelas cujo programa ou titulo combina com o que a pessoa disse; nunca as protegidas."""
    q = _norm(query)
    if len(q) < 3:
        return []
    found = []
    for hwnd, title, exe in wins:
        if any(p in _norm(exe) for p in PROTECTED) or "jefrey" in _norm(title):
            continue
        if q in _norm(exe) or q in _norm(title):
            found.append((hwnd, title, exe))
    return found


def clean_url(text: str) -> Optional[str]:
    """Endereco seguro para abrir, ou None. So http(s), com ponto no nome e sem usuario/senha."""
    t = (text or "").strip().strip("\"'")
    if _norm(t) in SITES:
        return SITES[_norm(t)]
    if not re.match(r"^https?://", t, re.I):
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", t, re.I):
            t = "https://" + t
        else:
            return None
    p = urlsplit(t)
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname or p.username or p.password or len(t) > 500:
        return None
    if p.hostname in ("localhost",) or re.match(r"^(127\.|10\.|192\.168\.|169\.254\.|0\.)", p.hostname) or p.hostname.endswith((".local", ".internal")):
        return None
    return t

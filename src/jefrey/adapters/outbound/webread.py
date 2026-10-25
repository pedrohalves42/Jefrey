"""Leitor de paginas e busca na web, protegidos.

- so http/https; bloqueia enderecos internos pelo IP RESOLVIDO (mesma regra do resto do Jefrey), a cada redirecionamento;
- limite de tamanho, de tempo e de redirecionamentos; so texto (HTML/texto puro);
- devolve TEXTO PURO: nada e executado e nada do que esta na pagina vira instrucao (quem usa deve tratar como dado).
Limite conhecido: o DNS e conferido antes de conectar (nao ha "pinagem" do IP); para o uso (estudar paginas publicas
num computador pessoal) o risco restante e baixo.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlparse

import httpx

from src.jefrey.domain.urls import site_domain

logger = logging.getLogger(__name__)

MAX_BYTES = 1_500_000
MAX_TEXT = 9000
MAX_REDIRECTS = 3
TIMEOUT_S = 10.0
_UA = "Mozilla/5.0 (compatible; Jefrey/1.0; assistente pessoal)"
_OK_TYPES = ("text/html", "application/xhtml", "text/plain")


class ReadError(Exception):
    """Mensagem curta e segura para registro; nunca mostrada crua a pessoa."""


_SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "aside", "form", "iframe", "template", "head"}
_BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "tr", "section", "article", "blockquote", "pre", "table"}


class _Extract(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in _SKIP:
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in _SKIP and self._skip:
            self._skip -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str, limit: int = MAX_TEXT) -> tuple[str, str]:
    """(titulo, texto) de uma pagina. Texto sem tags, linhas curtas demais descartadas."""
    p = _Extract()
    try:
        p.feed(html)
        p.close()
    except Exception:  # HTML quebrado: usa o que deu
        pass
    lines = [" ".join(s.split()) for s in "".join(p.parts).splitlines()]
    kept = [ln for ln in lines if len(ln) >= 25 or (ln and ln[-1] in ".!?:")]
    text = "\n".join(kept)
    return " ".join(p.title.split())[:200], text[:limit]


def _default_blocked(url: str) -> bool:
    from src.jefrey.core.connections import _is_blocked_url

    return _is_blocked_url(url)


async def fetch_page(url: str, *, transport: Optional[httpx.AsyncBaseTransport] = None,
                     blocked: Callable[[str], bool] = _default_blocked) -> dict:
    """Le uma pagina publica e devolve {url, title, text, fetched_at}. Levanta ReadError se nao for seguro/possivel."""
    current = url.strip()
    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False, transport=transport,
                                 headers={"User-Agent": _UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5"}) as c:
        for _ in range(MAX_REDIRECTS + 1):
            if len(current) > 2048 or await asyncio.to_thread(blocked, current):
                raise ReadError("endereco nao permitido")
            try:
                async with c.stream("GET", current) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        loc = r.headers.get("location")
                        if not loc:
                            raise ReadError("redirecionamento sem destino")
                        current = urljoin(current, loc)
                        continue
                    if r.status_code != 200:
                        raise ReadError(f"status {r.status_code}")
                    ctype = r.headers.get("content-type", "").lower()
                    if not ctype.startswith(_OK_TYPES):
                        raise ReadError("tipo de conteudo nao suportado")
                    buf = bytearray()
                    async for chunk in r.aiter_bytes():
                        buf += chunk
                        if len(buf) > MAX_BYTES:
                            break
                    enc = r.encoding or "utf-8"
            except httpx.HTTPError as e:
                raise ReadError(type(e).__name__)
            html = bytes(buf[:MAX_BYTES]).decode(enc, errors="replace")
            title, text = html_to_text(html) if "html" in ctype else ("", html[:MAX_TEXT])
            if len(text) < 200:
                raise ReadError("pagina sem texto util")
            return {"url": current, "title": title or urlparse(current).netloc, "text": text,
                    "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    raise ReadError("redirecionamentos demais")


def _ddg(query: str, n: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore[no-redef]
    with DDGS() as d:
        return list(d.text(query, region="br-pt", max_results=n))


async def web_search(query: str, n: int = 6, searcher: Optional[Callable[[str, int], list[dict]]] = None,
                     blocked: Callable[[str], bool] = _default_blocked) -> list[dict]:
    """[{title, url, snippet}] sem enderecos internos. Falha de rede vira lista vazia."""
    q = " ".join((query or "").split())[:200]
    if not q:
        return []
    try:
        raw = await asyncio.to_thread(searcher or _ddg, q, n)
    except Exception as e:
        logger.info("busca na web indisponivel (%s)", type(e).__name__)
        return []
    out: list[dict] = []
    for r in raw or []:
        url = str(r.get("href") or r.get("url") or "")
        if not url.startswith(("http://", "https://")) or await asyncio.to_thread(blocked, url):
            continue
        out.append({"title": " ".join(str(r.get("title") or "").split())[:160], "url": url,
                    "snippet": " ".join(str(r.get("body") or r.get("snippet") or r.get("content") or "").split())[:300]})
    return out[:n]


def domain(url: str) -> str:
    return site_domain(url)

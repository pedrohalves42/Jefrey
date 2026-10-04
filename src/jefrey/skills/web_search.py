"""Skill: Busca Web via Tavily + DuckDuckGo fallback (P1.1 AXIOM+CIPHER)."""
from __future__ import annotations
from typing import Final
import asyncio
import os
import time
import logging

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)

CACHE_TTL: Final[float] = 300.0
TIMEOUT_S: Final[float] = 10.0

class WebSearchSkill(SkillBase):
    metadata = SkillMetadata(
        name="web_search",
        description="Busca informacoes atuais na web via Tavily (fallback DuckDuckGo, cache 5m, timeout 10s)",
        tags=["web", "search", "research", "news"],
        requires_auth=True,
        enabled_by_default=True,
    )

    def __init__(self) -> None:
        super().__init__()
        self._client = None
        self._cache: dict[str, tuple[float, dict]] = {}

    def _cache_get(self, key: str) -> dict | None:
        item = self._cache.get(key)
        if item and (time.time() - item[0] < CACHE_TTL):
            try:
                from src.jefrey.core.metrics import WEB_SEARCH_CACHE_HIT
                WEB_SEARCH_CACHE_HIT.labels(mode="hit").inc()
            except Exception as _e:
                logger.debug("ignorado (%s): %s", 'web_search.py', type(_e).__name__)
            return item[1]
        return None

    def _cache_set(self, key: str, value: dict) -> None:
        self._cache[key] = (time.time(), value)
        # prune if large (High Performance Python: bounded cache)
        if len(self._cache) > 200:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            self._cache.pop(oldest, None)

    def initialize(self) -> bool:
        api_key = os.getenv("JEFREY_TAVILY_API_KEY") or os.getenv("TAVILY_API_KEY") or os.getenv("JEFREY_TAVILY__API_KEY")
        if not api_key:
            logger.warning("JEFREY_TAVILY_API_KEY nao configurado - web_search em modo fallback DuckDuckGo")
            # still READY via DuckDuckGo fallback, but mark skip for Tavily
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="web_search", status="skip").inc()
            except Exception as _e:
                logger.debug("ignorado (%s): %s", 'web_search.py', type(_e).__name__)
            # allow DDG fallback without Tavily
            self._client = None
          
        try:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=api_key)
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="web_search", status="ok").inc()
            except Exception as _e:
                logger.debug("ignorado (%s): %s", 'web_search.py', type(_e).__name__)
            return True
        except ImportError:
            logger.warning("tavily-python nao instalado: pip install tavily-python (usando fallback DuckDuckGo)")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="web_search", status="skip").inc()
            except Exception as _e:
                logger.debug("ignorado (%s): %s", 'web_search.py', type(_e).__name__)
            self._client = None
            return True
        except Exception as e:
            logger.warning(f"WebSearchSkill init Tavily falhou, usando fallback DuckDuckGo: {type(e).__name__}")
            self._client = None
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="web_search", status="skip").inc()
            except Exception as _e:
                logger.debug("ignorado (%s): %s", 'web_search.py', type(_e).__name__)
            return True

    def get_tools(self) -> list:
        # Always expose tools - fallback handles missing Tavily
        return [self.search, self.search_news, self.extract]

    def _fallback_ddg(self, query: str, max_results: int = 5, news: bool = False) -> dict:
        """Busca sem chave (DuckDuckGo), em portugues do Brasil. Bloqueante: chame com asyncio.to_thread."""
        try:
            try:
                from ddgs import DDGS  # type: ignore[import-not-found]  # renamed package (preferred)
            except ImportError:
                from duckduckgo_search import DDGS  # type: ignore[import-not-found, no-redef]  # fallback compat
            with DDGS() as ddgs:
                results = list(ddgs.news(query, region="br-pt", max_results=max_results) if news
                               else ddgs.text(query, region="br-pt", max_results=max_results))
            # normalize to Tavily-like format (com data quando houver: a resposta deve citar fonte e data)
            norm = [{"title": r.get("title"), "url": r.get("href") or r.get("url"), "content": r.get("body"), "score": 0.5,
                     "published": r.get("date"), "site": r.get("source")} for r in results]
            return {"query": query, "answer": None, "results": norm, "source": "duckduckgo"}
        except Exception as e:
            logger.warning(f"DuckDuckGo fallback falhou: {type(e).__name__}")
            return {"error": "A busca na web nao respondeu agora.", "query": query, "results": []}

    @tool(description="Busca geral na web - retorna resposta direta + fontes")
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Busca web via Tavily com fallback DuckDuckGo e cache 5m."""
        cache_key = f"search:{query}:{max_results}:{search_depth}"
        _uid = user_id or "system"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if self._client:
            try:
                # Tavily with timeout if supported
                try:
                    result = self._client.search(
                        query=query,
                        max_results=max_results,
                        search_depth=search_depth,
                        include_domains=include_domains,
                        exclude_domains=exclude_domains,
                        include_answer=True,
                        include_raw_content=False,
                        include_images=False,
                        timeout=TIMEOUT_S,
                    )
                except TypeError:
                    result = self._client.search(
                        query=query,
                        max_results=max_results,
                        search_depth=search_depth,
                        include_domains=include_domains,
                        exclude_domains=exclude_domains,
                        include_answer=True,
                        include_raw_content=False,
                        include_images=False,
                    )
                out = {
                    "query": query,
                    "answer": result.get("answer"),
                    "results": result.get("results", []),
                    "response_time": result.get("response_time"),
                    "source": "tavily",
                }
                self._cache_set(cache_key, out)
                logger.info(f"Web search: '{query}' -> {len(out['results'])} resultados (tavily)")
                return out
            except Exception as e:
                logger.warning(f"Tavily search falhou, fallback DDG: {type(e).__name__}")
        # fallback (em outra thread: a biblioteca bloqueia e travaria a API inteira)
        out = await asyncio.to_thread(self._fallback_ddg, query, max_results)
        if not out.get("error"):
            self._cache_set(cache_key, out)
        return out

    @tool(description="Busca noticias recentes (ultimos 7 dias por padrao)")
    async def search_news(
        self,
        query: str,
        max_results: int = 5,
        days: int = 7,
        user_id: str | None = None,
    ) -> dict:
        """Busca noticias via Tavily com fallback."""
        cache_key = f"news:{query}:{max_results}:{days}"
        _uid = user_id or "system"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if self._client:
            try:
                try:
                    result = self._client.search(
                        query=query,
                        max_results=max_results,
                        search_depth="advanced",
                        topic="news",
                        days=days,
                        include_answer=True,
                        timeout=TIMEOUT_S,
                    )
                except TypeError:
                    result = self._client.search(
                        query=query,
                        max_results=max_results,
                        search_depth="advanced",
                        topic="news",
                        days=days,
                        include_answer=True,
                    )
                out = {"query": query, "answer": result.get("answer"), "results": result.get("results", []), "source": "tavily"}
                self._cache_set(cache_key, out)
                return out
            except Exception as e:
                logger.warning(f"Tavily news falhou, fallback DDG: {type(e).__name__}")
        out = await asyncio.to_thread(self._fallback_ddg, query, max_results, True)
        if not out.get("results") and not out.get("error"):  # sem noticias recentes: tenta a busca comum
            out = await asyncio.to_thread(self._fallback_ddg, query, max_results)
        if not out.get("error"):
            self._cache_set(cache_key, out)
        return out

    @tool(description="Le o texto de paginas da web (ate 3 enderecos) para responder com base na fonte")
    async def extract(self, urls: list[str], user_id: str | None = None) -> dict:
        """Le paginas com o leitor protegido (bloqueia enderecos internos, limita tamanho). Nao precisa de chave."""
        from src.jefrey.core import webread

        results, errors = [], []
        for url in [u for u in (urls or []) if isinstance(u, str)][:3]:
            try:
                p = await webread.fetch_page(url)
                results.append({"url": p["url"], "title": p["title"], "content": p["text"][:6000], "date": p["fetched_at"]})
            except webread.ReadError:
                errors.append(url)
        if not results:
            return {"error": "Nao consegui ler essas paginas.", "urls": errors}
        return {"results": results, "unreadable": errors}

@skill("web_search", "Busca web via Tavily com fallback DuckDuckGo", tags=["web", "search"], requires_auth=True)
class _WebSearchWrapper(WebSearchSkill):
    pass
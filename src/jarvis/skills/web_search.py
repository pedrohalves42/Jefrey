"""Skill: Busca Web (Tavily)."""
from __future__ import annotations
from typing import Any
import os
import logging

from src.jarvis.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)


class WebSearchSkill(SkillBase):
    metadata = SkillMetadata(
        name="web_search",
        description="Busca informações atuais na web via Tavily",
        tags=["web", "search", "research"],
        requires_auth=True,
    )
    
    def __init__(self):
        super().__init__()
        self._client = None
    
    async def initialize(self) -> bool:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            logger.warning("TAVILY_API_KEY não configurado - web_search desabilitado")
            return False
        
        try:
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=api_key)
            return True
        except ImportError:
            logger.error("tavily-python não instalado: pip install tavily-python")
            return False
    
    def get_tools(self) -> list:
        if not self._client:
            return []
        return [self.search, self.search_news, self.extract]
    
    @tool(description="Busca geral na web")
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> dict:
        """Busca web via Tavily."""
        try:
            result = self._client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                include_answer=True,
                include_raw_content=False,
            )
            return {
                "query": query,
                "answer": result.get("answer"),
                "results": result.get("results", []),
                "response_time": result.get("response_time"),
            }
        except Exception as e:
            logger.error(f"Erro na busca: {e}")
            return {"error": str(e), "query": query}
    
    @tool(description="Busca notícias recentes")
    async def search_news(
        self,
        query: str,
        max_results: int = 5,
        days: int = 7,
    ) -> dict:
        """Busca notícias."""
        try:
            result = self._client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                topic="news",
                days=days,
                include_answer=True,
            )
            return {
                "query": query,
                "answer": result.get("answer"),
                "results": result.get("results", []),
            }
        except Exception as e:
            return {"error": str(e), "query": query}
    
    @tool(description="Extrai conteúdo completo de URLs")
    async def extract(self, urls: list[str]) -> dict:
        """Extrai conteúdo de URLs."""
        try:
            result = self._client.extract(urls=urls)
            return {"results": result.get("results", [])}
        except Exception as e:
            return {"error": str(e), "urls": urls}


@skill("web_search", "Busca web via Tavily", tags=["web", "search"], requires_auth=True)
class _WebSearchWrapper(WebSearchSkill):
    pass
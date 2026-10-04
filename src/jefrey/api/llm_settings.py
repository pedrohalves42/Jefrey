"""Escolha do modelo pela interface: local (Ollama) ou nuvem (Claude, OpenAI e compativeis)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.jefrey.core.hardware import TIERS, read_memory_gb, recommend_model
from src.jefrey.core.llm_provider import (
    LLMClient, LLMConfigError, PROVIDERS, config_from_settings, load_saved_key, save_override,
)

router = APIRouter(prefix="/settings/llm", tags=["settings"])

PRESETS = [
    {"id": "ollama-local", "label": "Local (Ollama)", "provider": "ollama",
     "base_url": "http://ollama:11434", "models": ["qwen3:1.7b", "qwen2.5:3b", "qwen2.5:7b", "llama3.2:3b", "qwen2.5:0.5b"],
     "needs_key": False},
    {"id": "anthropic", "label": "Claude (Anthropic)", "provider": "anthropic",
     "base_url": "https://api.anthropic.com", "models": ["claude-sonnet-4-5", "claude-haiku-4-5-20251001"],
     "needs_key": True},
    {"id": "openai", "label": "ChatGPT (OpenAI)", "provider": "openai",
     "base_url": "https://api.openai.com", "models": ["gpt-4o-mini", "gpt-4o"], "needs_key": True},
    {"id": "openai-compat", "label": "Outro (compativel com OpenAI)", "provider": "openai",
     "base_url": "http://host.docker.internal:1234", "models": [], "needs_key": False},
]


class LLMUpdate(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=200)
    base_url: Optional[str] = Field(default=None, max_length=300)
    temperature: Optional[float] = None
    api_key: Optional[str] = Field(default=None, max_length=500)  # None mantem, "" apaga


def _public_view() -> dict:
    c = config_from_settings()
    return {
        "provider": c.provider, "model": c.model, "base_url": c.base_url,
        "temperature": c.temperature, "has_key": bool(c.api_key), "is_cloud": c.is_cloud,
        "providers": list(PROVIDERS),
    }


@router.get("")
async def get_llm():
    """Configuracao atual. A chave nunca e devolvida, so se existe."""
    return _public_view()


@router.get("/presets")
async def presets():
    return {"presets": PRESETS}


@router.get("/recommend")
async def recommend():
    """Modelo local ideal para a memoria disponivel agora, com a lista de opcoes."""
    total, avail = read_memory_gb()
    rec = recommend_model(avail)
    return {
        "memory_total_gb": round(total, 1), "memory_available_gb": round(avail, 1),
        "recommended": {"model": rec.model, "size_gb": rec.size_gb, "quality": rec.quality,
                        "needs_gb": rec.needs_gb, "tools": rec.tools},
        "options": [{"model": t.model, "size_gb": t.size_gb, "needs_gb": t.needs_gb,
                     "quality": t.quality, "tools": t.tools, "fits": avail >= t.needs_gb} for t in TIERS],
        "note": "Cada modelo precisa de mais memoria que o seu tamanho (contexto + sistema). "
                "Feche outros programas para liberar RAM ou use um provedor em nuvem.",
    }


@router.put("")
async def put_llm(body: LLMUpdate):
    try:
        save_override(body.provider, body.model, body.base_url, body.temperature, body.api_key)
        c = config_from_settings()
        LLMClient(c)  # valida (ex.: nuvem sem chave) antes de aceitar
    except LLMConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _public_view()


@router.post("/test")
async def test_llm():
    """Testa a conexao com o provedor atual sem enviar dados do usuario."""
    try:
        return await LLMClient(config_from_settings()).health()
    except LLMConfigError as e:
        return {"ok": False, "detail": str(e)}

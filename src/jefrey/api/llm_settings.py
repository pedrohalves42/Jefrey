"""Escolha do modelo pela interface: local (Ollama) ou nuvem (Claude, OpenAI e compativeis)."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from src.jefrey.core.hardware import TIERS, detect_gpu, local_advice, read_memory_gb, recommend_model
from src.jefrey.core.llm_provider import (
    LLMClient, LLMConfigError, MAX_FALLBACKS, PROVIDERS, config_from_settings, load_fallback_configs,
    load_override, save_fallbacks, save_override,
)

logger = logging.getLogger(__name__)
OPENROUTER_AUTH = "https://openrouter.ai/auth"
OPENROUTER_KEYS = "https://openrouter.ai/api/v1/auth/keys"
OPENROUTER_BASE = "https://openrouter.ai/api"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-6-luna"
PKCE_TTL_S = 600
_pkce: dict[str, tuple[str, float]] = {}  # state -> (code_verifier, expira)

router = APIRouter(prefix="/settings/llm", tags=["settings"])

# Modelos conferidos no catalogo publico do OpenRouter em 04/10/2026 (precos por milhao de tokens: luna 0,1/0,5 USD;
# gemini flash 0,75/3,75; claude sonnet 2/10). Nomes diretos de Anthropic/OpenAI: confira no painel do provedor.
PRESETS = [
    {"id": "openrouter", "label": "OpenRouter (um login, varios modelos)", "provider": "openai",
     "base_url": OPENROUTER_BASE, "models": [OPENROUTER_DEFAULT_MODEL, "google/gemini-3.8-flash", "anthropic/claude-sonnet-5.5",
                                             "openrouter/auto"],
     "needs_key": True, "one_click": True, "recommended": True},
    {"id": "anthropic", "label": "Claude (Anthropic)", "provider": "anthropic",
     "base_url": "https://api.anthropic.com", "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5-20251001"],
     "needs_key": True},
    {"id": "openai", "label": "ChatGPT (OpenAI)", "provider": "openai",
     "base_url": "https://api.openai.com", "models": ["gpt-6-luna", "gpt-6.1-sol"], "needs_key": True},
    {"id": "ollama-local", "label": "No meu computador (Ollama)", "provider": "ollama",
     "base_url": "http://ollama:11434", "models": ["qwen3:1.7b", "qwen2.5:3b", "gemma4:e2b", "gemma4:e4b"],
     "needs_key": False},
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
        "configured": bool(load_override().get("provider")),  # false = primeira execucao: mostrar o assistente
        "fallbacks": len(load_fallback_configs()),
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


# ---------------------------------------------------------------- sugestao de modelo local
@router.get("/advice")
async def advice():
    """Nuvem e o padrao; so sugere modelo local se houver placa de video capaz."""
    total, _ = read_memory_gb()
    out = local_advice(detect_gpu(), total)
    out["default"] = "cloud"
    out["ram_total_gb"] = round(total, 1)
    return out


# ---------------------------------------------------------------- reservas (se o principal falhar, usa o proximo)
class FallbackItem(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    provider: str
    model: str = Field(min_length=1, max_length=200)
    base_url: Optional[str] = Field(default=None, max_length=300)
    api_key: Optional[str] = Field(default=None, max_length=500)  # None mantem, "" apaga


@router.get("/fallbacks")
async def get_fallbacks():
    """Reservas configuradas. As chaves nunca sao devolvidas."""
    items = (load_override().get("fallbacks") or [])[:MAX_FALLBACKS]
    cfgs = load_fallback_configs()
    keyed = {(c.provider, c.model) for c in cfgs if c.api_key}
    return {"fallbacks": [{"id": i.get("id"), "provider": i.get("provider"), "model": i.get("model"),
                           "base_url": i.get("base_url"), "has_key": (i.get("provider"), i.get("model")) in keyed}
                          for i in items if isinstance(i, dict)], "max": MAX_FALLBACKS}


@router.put("/fallbacks")
async def put_fallbacks(items: list[FallbackItem]):
    try:
        save_fallbacks([i.model_dump() for i in items])
    except LLMConfigError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await get_fallbacks()


# ---------------------------------------------------------------- OpenRouter: login de 1 clique (chave e do proprio usuario)
def _purge_pkce(now: float) -> None:
    for k in [k for k, (_, exp) in _pkce.items() if exp < now]:
        _pkce.pop(k, None)
    while len(_pkce) > 20:
        _pkce.pop(next(iter(_pkce)))


@router.post("/openrouter/start")
async def openrouter_start(request: Request):
    """Devolve o endereco para a pessoa entrar no OpenRouter e autorizar o Jefrey (PKCE + state)."""
    now = time.time()
    verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(24)
    _pkce[state] = (verifier, now + PKCE_TTL_S)
    _purge_pkce(now)  # depois de inserir: o teto vale incluindo o novo
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    callback = str(request.base_url).rstrip("/") + "/settings/llm/openrouter/callback"
    from urllib.parse import urlencode
    q = urlencode({"callback_url": callback, "code_challenge": challenge, "code_challenge_method": "S256", "state": state})
    return {"auth_url": f"{OPENROUTER_AUTH}?{q}"}


@router.get("/openrouter/callback")
async def openrouter_callback(request: Request, code: str = "", state: str = ""):
    """Volta do OpenRouter (navegacao, sem login do Jefrey): protegida pelo `state` aleatorio de uso unico."""
    entry = _pkce.pop(state, None)
    if not code or entry is None or entry[1] < time.time():
        return RedirectResponse("/bem-vindo?erro=openrouter", status_code=303)
    try:
        from src.jefrey.adapters.outbound.weather_source import openrouter_key

        key = await openrouter_key(code, entry[0], OPENROUTER_KEYS)
        if not key:
            raise ValueError("sem chave")
        from src.jefrey.core import brains

        try:
            brains.attach_oneclick("openrouter", key)  # vira o principal; o cerebro anterior (se havia) vira reserva
        except Exception as e:
            logger.info("openrouter: reserva nao aplicada (%s); gravando so o principal", type(e).__name__)
            save_override("openai", OPENROUTER_DEFAULT_MODEL, OPENROUTER_BASE, None, key)
    except Exception as e:  # nunca registra codigo nem chave
        logger.warning("openrouter callback falhou: %s", type(e).__name__)
        return RedirectResponse("/bem-vindo?erro=openrouter", status_code=303)
    return RedirectResponse("/?conectado=openrouter", status_code=303)


# ---------------------------------------------------------------- baixar modelo local (com progresso)
class PullBody(BaseModel):
    models: list[str] = Field(min_length=1, max_length=3)


@router.post("/pull")
async def pull(body: PullBody):
    """Baixa modelos locais em segundo plano. 409 com mensagem clara se o Ollama nao esta instalado/rodando."""
    import asyncio
    from src.jefrey.core import model_pull

    try:
        return await asyncio.to_thread(model_pull.start, body.models)
    except model_pull.PullError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/pull-status")
async def pull_status():
    from src.jefrey.core import model_pull

    return model_pull.status()

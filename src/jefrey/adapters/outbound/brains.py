"""Cerebros do Jefrey, para leigos: varios servicos conectados ao mesmo tempo, com reserva automatica.

Por baixo usa o que ja existia (um principal + ate 3 reservas, chaves protegidas pelo Windows). Aqui fica o catalogo
em linguagem simples, a conexao guiada (validar o codigo, testar, guardar), trocar o principal e desconectar.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
from urllib.parse import urlsplit

from src.jefrey.core import llm_provider as P
from src.jefrey.core.secret_store import read_secret, valid_id, write_secret


class BrainError(Exception):
    """Mensagem pronta para a tela (portugues simples)."""


# kind: oneclick (entra no site e volta) | key (cola um codigo) | local (neste computador)
CATALOG: list[dict[str, Any]] = [
    {"id": "9router", "name": "9router", "tagline": "O seu roteador de cérebros, já instalado neste computador. Recomendado.", "kind": "key", "recommended": True,
     "provider": "openai", "base_url": "http://127.0.0.1:20128", "model": "gamehouse", "prefix": "",
     "key_url": "http://127.0.0.1:20128/dashboard"},
    {"id": "gemini", "name": "Gemini", "tagline": "Do Google. Tem plano gratuito.", "kind": "key", "recommended": True,
     "provider": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash", "prefix": "",  # as chaves novas do AI Studio nem sempre comecam com AIza
     "key_url": "https://aistudio.google.com/apikey"},
    {"id": "openrouter", "name": "OpenRouter", "tagline": "Um login só dá acesso a vários cérebros.", "kind": "oneclick",
     "provider": "openai", "base_url": "https://openrouter.ai/api", "model": "openai/gpt-6-luna", "prefix": "sk-or-",
     "key_url": "https://openrouter.ai/keys"},
    {"id": "anthropic", "name": "Claude", "tagline": "Da Anthropic. Ótimo para conversar e escrever.", "kind": "key",
     "provider": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-5-5", "prefix": "sk-ant-",
     "key_url": "https://console.anthropic.com/settings/keys"},
    {"id": "openai", "name": "ChatGPT", "tagline": "Da OpenAI.", "kind": "key",
     "provider": "openai", "base_url": "https://api.openai.com", "model": "gpt-6-luna", "prefix": "sk-",
     "key_url": "https://platform.openai.com/api-keys"},
    {"id": "groq", "name": "Groq", "tagline": "Muito rápido e tem plano gratuito.", "kind": "key",
     "provider": "openai", "base_url": "https://api.groq.com/openai", "model": "openai/gpt-oss-120b", "prefix": "gsk_",
     "key_url": "https://console.groq.com/keys"},
    {"id": "deepseek", "name": "DeepSeek", "tagline": "Muito barato.", "kind": "key",
     "provider": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-chat", "prefix": "sk-",
     "key_url": "https://platform.deepseek.com/api_keys"},
    {"id": "mistral", "name": "Mistral", "tagline": "Empresa europeia.", "kind": "key",
     "provider": "openai", "base_url": "https://api.mistral.ai", "model": "mistral-large-latest", "prefix": "",
     "key_url": "https://console.mistral.ai/api-keys"},
    {"id": "xai", "name": "Grok", "tagline": "Da xAI.", "kind": "key",
     "provider": "openai", "base_url": "https://api.x.ai", "model": "grok-4", "prefix": "xai-",
     "key_url": "https://console.x.ai"},
    {"id": "local", "name": "Neste computador", "tagline": "Sem internet e sem custo, mas as respostas são mais simples.", "kind": "local",
     "provider": "ollama", "base_url": "", "model": "qwen3:1.7b", "prefix": "", "key_url": ""},
]
_BY_ID = {b["id"]: b for b in CATALOG}
MAX_BRAINS = 1 + P.MAX_FALLBACKS


def public_catalog() -> list[dict]:
    return [{k: b[k] for k in ("id", "name", "tagline", "kind", "key_url")} | {"recommended": bool(b.get("recommended"))} for b in CATALOG]


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def identify(provider: str, base_url: str) -> str:
    """Qual cartao do catalogo corresponde a esta configuracao ('custom' se nenhum)."""
    if provider == "ollama":
        return "local"
    h = _host(base_url)
    for b in CATALOG:
        if b["provider"] == provider and b["base_url"] and _host(b["base_url"]) == h:
            return b["id"]
    return "custom"


def key_problem(brain_id: str, key: str) -> Optional[str]:
    """Texto humano se o codigo colado nao serve para este cerebro; None se parece certo."""
    b = _BY_ID.get(brain_id)
    if b is None or b["kind"] == "local":
        return "Esse cérebro não precisa de código."
    k = (key or "").strip().strip("\"'`").strip()
    if not k:
        return "Cole aqui o código que você copiou."
    if re.search(r"\s", k):
        return "O código não pode ter espaços no meio. Copie de novo, o código inteiro."
    if len(k) < 20:
        return "O código parece cortado. Copie de novo, o código inteiro."
    # um prefixo mais especifico de OUTRO servico (ex.: sk-ant- e sk-or-, que tambem comecam com sk-) denuncia o cartao errado
    others = [o["name"] for o in CATALOG if o["id"] != brain_id and o["prefix"] and len(o["prefix"]) > len(b["prefix"]) and k.startswith(o["prefix"])]
    if others:
        return f"Esse código parece ser do {others[0]}, não do {b['name']}. Escolha o cartão certo."
    if b["prefix"] and not k.startswith(b["prefix"]):
        return f"O código do {b['name']} começa com “{b['prefix']}”. Copie de novo, no botão de copiar do site."
    return None


# ---------------- estado ----------------
def _primary_key() -> Optional[str]:
    return P.load_saved_key()


def state() -> dict:
    """Quem esta conectado, quem e o principal e quem e reserva. Nunca devolve chaves."""
    ov = P.load_override()
    out: list[dict] = []
    if ov.get("provider"):
        cfg = P.config_from_settings()
        bid = identify(cfg.provider, cfg.base_url)
        if cfg.provider == "ollama" or cfg.api_key:
            out.append({"id": bid, "role": "principal", "model": cfg.model})
    for it in (ov.get("fallbacks") or [])[: P.MAX_FALLBACKS]:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        if it.get("provider") == "ollama" or read_secret(P._fallback_key_file(str(it["id"]))):
            out.append({"id": str(it["id"]), "role": "reserva", "model": str(it.get("model"))})
    from src.jefrey.domain.llm_roles import ROLES, TEAM_ROLES

    saved = P.load_roles()
    for b in out:
        b["roles"] = saved.get(b["id"], list(ROLES))  # sem registro: serve para tudo
        b["all_roles"] = b["id"] not in saved
    return {"brains": out, "catalog": public_catalog(), "max": MAX_BRAINS, "machine": machine(),
            "roles": [{"id": k, "label": v} for k, v in ROLES.items()], "team": P.load_team(), "team_roles": list(TEAM_ROLES)}


LOCAL_MIN_RAM_GB = 24.0  # abaixo disso, modelo local costuma ser fraco/lento: a conta na nuvem e a melhor escolha


def machine() -> dict:
    """Conta na nuvem e o padrao; o cerebro local so e sugerido se o computador aguentar modelos maiores."""
    try:
        from src.jefrey.core import sysinfo

        total = sysinfo.memory()[1]
    except Exception:
        total = 0.0
    return {"ram_gb": total, "local_recommended": total >= LOCAL_MIN_RAM_GB}


def _entries() -> list[dict]:
    """Principal primeiro, depois as reservas, com chave (uso interno)."""
    ov = P.load_override()
    items: list[dict] = []
    if ov.get("provider"):
        cfg = P.config_from_settings()
        items.append({"id": identify(cfg.provider, cfg.base_url), "provider": cfg.provider, "model": cfg.model,
                      "base_url": ov.get("base_url") or None, "api_key": _primary_key()})
    for it in (ov.get("fallbacks") or [])[: P.MAX_FALLBACKS]:
        if isinstance(it, dict) and it.get("id"):
            items.append({"id": str(it["id"]), "provider": it.get("provider"), "model": it.get("model"), "base_url": it.get("base_url"),
                          "api_key": read_secret(P._fallback_key_file(str(it["id"])))})
    return items


def _apply(items: list[dict]) -> None:
    """Grava a lista (principal primeiro). Chaves explicitas; reservas limitadas pelo programa."""
    items = items[:MAX_BRAINS]
    if not items:
        _clear()
        return
    head, rest = items[0], items[1:]
    P.save_override(head["provider"], head["model"], head.get("base_url"), None, head.get("api_key") or "")
    P.save_fallbacks([{"id": r["id"], "provider": r["provider"], "model": r["model"], "base_url": r.get("base_url"),
                       "api_key": r.get("api_key") or ""} for r in rest])


def _clear() -> None:
    f = P._override_file()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    for k in ("provider", "model", "base_url", "fallbacks"):
        data.pop(k, None)
    if f.exists():
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    P._key_file().unlink(missing_ok=True)
    for old in (P._config_dir() / "credentials").glob("llm_key_*"):
        old.unlink(missing_ok=True)


def _entry_for(brain_id: str, key: Optional[str]) -> dict:
    b = _BY_ID[brain_id]
    return {"id": brain_id, "provider": b["provider"], "model": b["model"], "base_url": b["base_url"] or None, "api_key": key}


async def connect(brain_id: str, key: Optional[str], *, primary: Optional[bool] = None) -> dict:
    """Valida o codigo, testa de verdade, guarda e arruma a ordem. Levanta BrainError com texto para a tela."""
    b = _BY_ID.get(brain_id)
    if b is None or not valid_id(brain_id):
        raise BrainError("Não conheço esse cérebro.")
    clean: Optional[str] = None
    if b["kind"] != "local":
        problem = key_problem(brain_id, key or "")
        if problem:
            raise BrainError(problem)
        clean = (key or "").strip().strip("\"'`").strip()
    entry = _entry_for(brain_id, clean)
    base = entry["base_url"] or (os.getenv("JEFREY_LLM__BASE_URL") or "http://127.0.0.1:11434")  # local: o ambiente decide
    try:
        health = await P.LLMClient(P.LLMConfig(entry["provider"], entry["model"], P._normalize_base(entry["provider"], base), api_key=clean)).health()
    except P.LLMConfigError:
        raise BrainError("Não consegui usar esse código. Confira se copiou inteiro.")
    if not health.get("ok"):
        raise BrainError(_health_message(health))
    items = [e for e in _entries() if e["id"] != brain_id]
    first = not items
    if len(items) >= MAX_BRAINS:
        raise BrainError(f"Você já tem {MAX_BRAINS} cérebros conectados. Desconecte um para incluir outro.")
    if primary is None:
        primary = first  # o primeiro conectado vira o principal; os outros entram como reserva
    ordered = [entry] + items if primary else items + [entry]
    try:
        _apply(ordered)
    except P.LLMConfigError as e:
        raise BrainError(str(e))
    return state()


def _health_message(h: dict) -> str:
    d = str(h.get("detail", "")).lower()
    if "401" in d or "403" in d or "http 400" in d or "unauthor" in d or "invalid" in d:
        return "O serviço recusou esse código. Confira se copiou inteiro e se ainda está ativo."
    if "402" in d or "credit" in d or "billing" in d or "quota" in d:
        return "O código é válido, mas a conta está sem crédito. Adicione saldo no site do serviço."
    if "connect" in d or "timeout" in d:
        return "Não consegui chegar ao serviço. Verifique a sua internet."
    return "Não deu para conectar com esse código. Confira e tente de novo."


def explain_failure(e: Exception) -> str:
    """O motivo, em portugues simples, de um cerebro nao responder (sem chaves, sem URLs)."""
    import httpx

    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        body = ""
        try:
            body = e.response.text[:400].lower()
        except Exception:
            body = ""
        if code == 402 or "credit" in body or "insufficient" in body or "balance" in body or "quota" in body:
            return "sem saldo ou no limite: adicione crédito no site do serviço"
        if code == 429:
            return "muitas perguntas seguidas (limite do serviço): tente mais tarde"
        if code in (401, 403):
            return "o serviço recusou a chave: confira se ela está ativa"
        if code == 404 or "model" in body and ("not exist" in body or "not found" in body):
            return "esse modelo não existe mais ou a conta não tem acesso a ele: troque o modelo"
        return f"o serviço respondeu com erro {code}"
    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError)):
        return "não consegui chegar ao serviço (internet ou serviço fora do ar)"
    return "não respondeu agora"


async def check_all(timeout: float = 25.0) -> list[dict]:
    """Pergunta algo bem curto a cada cerebro (principal e reservas) ao mesmo tempo e conta quanto cada um demorou."""
    import asyncio
    import time

    ov = P.load_override()
    jobs: list[tuple[str, str, P.LLMConfig]] = []
    if ov.get("provider"):
        cfg = P.config_from_settings()
        if cfg.provider == "ollama" or cfg.api_key:
            jobs.append((identify(cfg.provider, cfg.base_url), "principal", cfg))
    fb = P.load_fallback_configs()
    ids = [str(i.get("id", "")) for i in (ov.get("fallbacks") or [])[: P.MAX_FALLBACKS] if isinstance(i, dict) and i.get("provider") in P.PROVIDERS and i.get("model")]
    for bid, cfg in zip(ids, fb):
        jobs.append((bid, "reserva", cfg))

    async def one(bid: str, role: str, cfg: "P.LLMConfig") -> dict:
        t0 = time.perf_counter()
        base = {"id": bid, "role": role, "model": cfg.model}
        try:
            await asyncio.wait_for(P.LLMClient(cfg).chat([{"role": "user", "content": "Responda só com a palavra: ok"}]), timeout=timeout)
            return {**base, "ok": True, "seconds": round(time.perf_counter() - t0, 2), "problem": ""}
        except asyncio.TimeoutError:
            return {**base, "ok": False, "seconds": round(time.perf_counter() - t0, 2), "problem": "demorou demais para responder"}
        except Exception as e:
            return {**base, "ok": False, "seconds": round(time.perf_counter() - t0, 2), "problem": explain_failure(e)}

    return list(await asyncio.gather(*[one(*j) for j in jobs]))


def make_primary(brain_id: str) -> dict:
    items = _entries()
    pick = next((e for e in items if e["id"] == brain_id), None)
    if pick is None:
        raise BrainError("Esse cérebro não está conectado.")
    _apply([pick] + [e for e in items if e["id"] != brain_id])
    return state()


def disconnect(brain_id: str) -> dict:
    items = _entries()
    if not any(e["id"] == brain_id for e in items):
        raise BrainError("Esse cérebro não está conectado.")
    _apply([e for e in items if e["id"] != brain_id])
    P.save_roles(brain_id, None)
    return state()


def set_roles(brain_id: str, roles: Optional[list]) -> dict:
    """Define o que este cerebro faz (None = serve para tudo). Lista vazia = so de reserva."""
    if not any(e["id"] == brain_id for e in _entries()):
        raise BrainError("Esse cérebro não está conectado.")
    P.save_roles(brain_id, None if roles is None else list(roles))
    return state()


def set_team(roles: list) -> dict:
    """Funcoes em que dois cerebros trabalham juntos (um escreve, outro revisa)."""
    P.save_team(list(roles))
    return state()


def attach_oneclick(brain_id: str, key: str) -> None:
    """Chamado quando o login de 1 clique volta com a chave: vira o principal e o antigo principal vira reserva."""
    entry = _entry_for(brain_id, key)
    items = [e for e in _entries() if e["id"] != brain_id]
    _apply([entry] + items)

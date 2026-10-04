"""Camada de provedores de LLM: local (Ollama) por padrao, nuvem opcional.

Provedores suportados (JEFREY_LLM__PROVIDER):
  - ollama:    API nativa /api/chat (local, padrao)
  - openai:    API compativel com OpenAI /v1/chat/completions (OpenAI, OpenRouter,
               LM Studio, llama.cpp, vLLM... basta mudar JEFREY_LLM__BASE_URL)
  - anthropic: API Messages /v1/messages (Claude)

A chave da nuvem vem de JEFREY_LLM__API_KEY e nunca e registrada em log.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import httpx

from src.jefrey.core.llm_tools import StreamItem, StreamParser, ToolCall, tool_defs, to_provider_messages

Message = dict[str, str]

PROVIDERS = ("ollama", "openai", "anthropic")

OPENAI_DEFAULT_URL = "https://api.openai.com"
ANTHROPIC_DEFAULT_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class LLMConfigError(RuntimeError):
    """Configuracao de LLM invalida (ex.: provedor de nuvem sem chave)."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000

    @property
    def is_cloud(self) -> bool:
        return self.provider in ("openai", "anthropic") and not _is_local_url(self.base_url)


def _is_local_url(url: str) -> bool:
    return any(h in url for h in ("localhost", "127.0.0.1", "host.docker.internal", "ollama:"))


# ---- override em tempo de execucao (escolhido pela interface) -----------------
def _config_dir() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config"))


def _override_file() -> Path:
    return _config_dir() / "llm.runtime.json"


def _key_file() -> Path:
    return _config_dir() / "credentials" / "llm_api_key"


DOCKER_OLLAMA_URL = "http://ollama:11434"  # nome do servico DENTRO do docker-compose; so existe la


def load_override() -> dict:
    try:
        data = json.loads(_override_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    # O endereco padrao do Ollama local e decidido pelo ambiente (docker ou nativo), nunca pelo arquivo:
    # arquivos antigos que guardaram o nome do container quebravam o chat fora do Docker.
    if (data.get("provider") or "ollama") == "ollama" and str(data.get("base_url") or "").rstrip("/") == DOCKER_OLLAMA_URL:
        data.pop("base_url", None)
    return data


def load_saved_key() -> Optional[str]:
    try:
        return _key_file().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def save_override(provider: str, model: str, base_url: Optional[str],
                  temperature: Optional[float], api_key: Optional[str]) -> None:
    """Grava escolha de modelo. api_key=None mantem a chave atual; "" apaga."""
    if provider not in PROVIDERS:
        raise LLMConfigError(f"provedor desconhecido: {provider}")
    if not model.strip():
        raise LLMConfigError("modelo nao pode ser vazio")
    # valida a configuracao RESULTANTE antes de gravar qualquer coisa
    prospective_key = load_saved_key() if api_key is None else (api_key.strip() or None)
    prospective_key = prospective_key or os.getenv("JEFREY_LLM__API_KEY")
    LLMClient(LLMConfig(provider, model.strip(), _normalize_base(provider, (base_url or "").strip()),
                        api_key=prospective_key))
    _config_dir().mkdir(parents=True, exist_ok=True)
    saved_base = (base_url or "").strip().rstrip("/") or None
    if provider == "ollama" and saved_base in (None, DOCKER_OLLAMA_URL):
        saved_base = None  # padrao: o ambiente decide
    data = {"provider": provider, "model": model.strip(), "base_url": saved_base}
    if temperature is not None:
        data["temperature"] = max(0.0, min(2.0, float(temperature)))
    _override_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if api_key is not None:
        kf = _key_file()
        kf.parent.mkdir(parents=True, exist_ok=True)
        if api_key.strip():
            kf.write_text(api_key.strip(), encoding="utf-8")
        elif kf.exists():
            kf.unlink()


def _normalize_base(provider: str, base: str) -> str:
    base = (base or "").rstrip("/")
    if provider == "openai" and (not base or "ollama" in base):
        return OPENAI_DEFAULT_URL
    if provider == "anthropic" and (not base or "ollama" in base):
        return ANTHROPIC_DEFAULT_URL
    if provider == "ollama" and not base:
        return "http://ollama:11434"
    return base


def config_from_settings(settings: Any = None) -> LLMConfig:
    """Constroi LLMConfig: settings/env, sobrescrito pelo que foi salvo na interface."""
    if settings is None:
        from src.jefrey.core.config import get_settings
        settings = get_settings()
    llm = _Merged(settings.llm, load_override())
    provider = (getattr(llm, "provider", None) or "ollama").lower()
    base = (getattr(llm, "base_url", None) or "").rstrip("/")
    if provider == "openai" and (not base or "ollama" in base):
        base = OPENAI_DEFAULT_URL
    elif provider == "anthropic" and (not base or "ollama" in base):
        base = ANTHROPIC_DEFAULT_URL
    elif provider == "ollama" and not base:
        base = "http://ollama:11434"
    return LLMConfig(
        provider=provider,
        model=getattr(llm, "model", "qwen2.5:0.5b"),
        base_url=base,
        api_key=load_saved_key() or getattr(llm, "api_key", None) or os.getenv("JEFREY_LLM__API_KEY"),
        temperature=float(getattr(llm, "temperature", 0.7)),
        max_tokens=int(getattr(llm, "max_tokens", 4000)),
    )


class _Merged:
    """Le atributos do override primeiro e cai para as settings."""
    def __init__(self, base: Any, override: dict):
        self._b, self._o = base, override

    def __getattr__(self, name: str) -> Any:
        v = self._o.get(name)
        return v if v not in (None, "") else getattr(self._b, name, None)


def _has_thinking_mode(model: str) -> bool:
    """Familias qwen3/qwen3.5 raciocinam por padrao (lento); no chat do Jefrey o raciocinio fica desligado."""
    return model.lower().startswith("qwen3")


def _timeout() -> float:
    return float(os.getenv("JEFREY_LLM_TIMEOUT", "90"))


def _split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    rest = [m for m in messages if m.get("role") != "system"]
    return system, rest


def _approx_tokens(text: str) -> int:
    """Estimativa (~4 caracteres por token); suficiente para acompanhar uso, nao para cobrar."""
    return max(1, len(text) // 4) if text else 0


class LLMClient:
    """Cliente unico para chat completo e em streaming."""

    def _record(self, started: float, messages: list[Message], output: str) -> None:
        """Registra latencia e tokens (estimados) no Prometheus. Nunca derruba a chamada."""
        try:
            from src.jefrey.core.metrics import LLM_LATENCY, LLM_TOKENS
            c = self.config
            LLM_LATENCY.labels(provider=c.provider, model=c.model).observe(time.monotonic() - started)
            LLM_TOKENS.labels(type="input", provider=c.provider, model=c.model).inc(
                _approx_tokens(" ".join(m.get("content", "") for m in messages)))
            LLM_TOKENS.labels(type="output", provider=c.provider, model=c.model).inc(_approx_tokens(output))
        except Exception:
            pass

    def __init__(self, config: LLMConfig, transport: Optional[httpx.AsyncBaseTransport] = None):
        if config.provider not in PROVIDERS:
            raise LLMConfigError(f"provedor desconhecido: {config.provider}")
        if config.provider == "anthropic" and not config.api_key:
            raise LLMConfigError("o provedor Claude (anthropic) exige uma chave de API")
        if config.provider == "openai" and not config.api_key and config.is_cloud:
            raise LLMConfigError("o provedor OpenAI (nuvem) exige uma chave de API")
        self.config = config
        self._transport = transport

    # ---- montagem de requisicao -------------------------------------------------
    def _request(self, messages: list[Message], stream: bool, tools: Optional[list[dict]] = None) -> tuple[str, dict, dict]:
        c = self.config
        system, msgs = to_provider_messages(c.provider, messages)
        defs = tool_defs(c.provider, tools) if tools else None
        if c.provider == "ollama":
            body: dict[str, Any] = {
                "model": c.model,
                "messages": msgs,
                "stream": stream,
                "options": {"temperature": c.temperature, "num_predict": c.max_tokens},
            }
            if defs:
                body["tools"] = defs
            if _has_thinking_mode(c.model):
                body["think"] = False
            return f"{c.base_url}/api/chat", {}, body
        base = c.base_url[:-3] if c.base_url.endswith("/v1") else c.base_url
        if c.provider == "openai":
            headers = {"Authorization": f"Bearer {c.api_key}"} if c.api_key else {}
            body = {
                "model": c.model,
                "messages": msgs,
                "stream": stream,
                "temperature": c.temperature,
                "max_tokens": c.max_tokens,
            }
            if defs:
                body["tools"] = defs
            return f"{base}/v1/chat/completions", headers, body
        body = {
            "model": c.model,
            "messages": msgs,
            "stream": stream,
            "temperature": c.temperature,
            "max_tokens": c.max_tokens,
        }
        if system:
            body["system"] = system
        if defs:
            body["tools"] = defs
        return (
            f"{base}/v1/messages",
            {"x-api-key": c.api_key or "", "anthropic-version": ANTHROPIC_VERSION},
            body,
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=_timeout(), transport=self._transport)

    # ---- chat completo ----------------------------------------------------------
    async def chat(self, messages: list[Message]) -> str:
        started = time.monotonic()
        url, headers, body = self._request(messages, stream=False)
        async with self._client() as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        text = self._extract_full(data)
        self._record(started, messages, text)
        return text

    def _extract_full(self, data: dict) -> str:
        p = self.config.provider
        if p == "ollama":
            return (data.get("message") or {}).get("content", "") or ""
        if p == "openai":
            choices = data.get("choices") or []
            return ((choices[0].get("message") or {}).get("content") or "") if choices else ""
        blocks = data.get("content") or []
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    # ---- streaming --------------------------------------------------------------
    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Somente texto (sem ferramentas)."""
        async for item in self.stream_events(messages):
            if isinstance(item, str):
                yield item

    async def stream_events(self, messages: list[Message], tools: Optional[list[dict]] = None) -> AsyncIterator[StreamItem]:
        """Texto (str) e chamadas de ferramenta (ToolCall) conforme chegam."""
        started = time.monotonic()
        out: list[str] = []
        parser = StreamParser(self.config.provider)
        url, headers, body = self._request(messages, stream=True, tools=tools)
        async with self._client() as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    for item in parser.feed(line):
                        if isinstance(item, str):
                            out.append(item)
                        yield item
                    if parser.done:
                        break
                for item in parser.flush():
                    yield item
        self._record(started, messages, "".join(out))

    def _parse_stream_line(self, line: str) -> tuple[str, bool]:
        """Retorna (texto, terminou). Linhas invalidas/vazias sao ignoradas."""
        line = line.strip()
        if not line:
            return "", False
        p = self.config.provider
        if p == "ollama":
            try:
                data = json.loads(line)
            except ValueError:
                return "", False
            return (data.get("message") or {}).get("content", "") or "", bool(data.get("done"))
        # openai e anthropic usam SSE: "data: {...}"
        if not line.startswith("data:"):
            return "", False
        payload = line[5:].strip()
        if payload == "[DONE]":
            return "", True
        try:
            data = json.loads(payload)
        except ValueError:
            return "", False
        if p == "openai":
            choices = data.get("choices") or []
            if not choices:
                return "", False
            return (choices[0].get("delta") or {}).get("content") or "", False
        kind = data.get("type")
        if kind == "content_block_delta":
            return (data.get("delta") or {}).get("text", "") or "", False
        return "", kind == "message_stop"

    # ---- diagnostico ------------------------------------------------------------
    async def health(self) -> dict:
        """Testa a conexao sem enviar dados do usuario."""
        c = self.config
        try:
            async with self._client() as client:
                if c.provider == "ollama":
                    r = await client.get(f"{c.base_url}/api/tags")
                    r.raise_for_status()
                    names = [m.get("name") for m in r.json().get("models", [])]
                    ok = any(n == c.model or (n or "").split(":")[0] == c.model.split(":")[0] and ":" not in c.model for n in names)
                    return {"ok": ok, "provider": c.provider, "model": c.model,
                            "detail": "modelo disponivel" if ok else f"modelo nao instalado; instalados: {names}"}
                if c.provider == "openai":
                    base = c.base_url[:-3] if c.base_url.endswith("/v1") else c.base_url
                    r = await client.get(f"{base}/v1/models",
                                         headers={"Authorization": f"Bearer {c.api_key}"} if c.api_key else {})
                    r.raise_for_status()
                    return {"ok": True, "provider": c.provider, "model": c.model, "detail": "conectado"}
                r = await client.get(f"{c.base_url}/v1/models",
                                     headers={"x-api-key": c.api_key or "", "anthropic-version": ANTHROPIC_VERSION})
                r.raise_for_status()
                return {"ok": True, "provider": c.provider, "model": c.model, "detail": "conectado"}
        except Exception as e:  # nunca incluir a chave na mensagem
            return {"ok": False, "provider": c.provider, "model": c.model,
                    "detail": f"{type(e).__name__}: indisponivel"}


def friendly_error(e: Exception) -> str:
    """Mensagem em portugues para o usuario; nunca expoe chaves ou URLs internas."""
    if isinstance(e, LLMConfigError):
        return f"Configuracao do modelo incompleta: {e}. Ajuste em Configuracoes."
    if isinstance(e, httpx.TimeoutException):
        return "O modelo demorou demais para responder. Tente de novo ou escolha um modelo menor/mais rapido."
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code in (401, 403):
            return "A chave de API foi recusada pelo provedor. Confira a chave em Configuracoes."
        if code == 404:
            return "Modelo nao encontrado no provedor. Verifique o nome do modelo (no Ollama: ollama pull <modelo>)."
        if code == 429:
            return "Limite de uso do provedor atingido. Aguarde um pouco ou troque de modelo."
        if code >= 500:
            return "O modelo falhou ao processar (provavel falta de memoria). Tente um modelo menor."
        return f"O provedor recusou o pedido (HTTP {code})."
    if isinstance(e, httpx.ConnectError):
        return "Nao consegui conectar ao modelo. Verifique se o Ollama esta rodando ou a URL do provedor."
    return f"O modelo esta indisponivel ({type(e).__name__})."


def get_llm_client() -> LLMClient:
    return LLMClient(config_from_settings())

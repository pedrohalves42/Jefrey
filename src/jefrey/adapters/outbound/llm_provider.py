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
import logging
import os
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import httpx

from src.jefrey.core.llm_tools import StreamItem, StreamParser, tool_defs, to_provider_messages

Message = dict[str, str]

logger = logging.getLogger(__name__)

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


ROUTER_PORT = ":20128"  # 9router: roteador local que leva a modelos da nuvem (conta como nuvem: cerebro completo, nao o pequeno local)


def _is_local_url(url: str) -> bool:
    if ROUTER_PORT in url and any(h in url for h in ("localhost", "127.0.0.1")):
        return False
    return any(h in url for h in ("localhost", "127.0.0.1", "host.docker.internal", "ollama:"))


def _chat_url(base: str) -> str:
    """Endereco do chat no formato OpenAI. O Gemini usa .../v1beta/openai/chat/completions (sem /v1)."""
    if "generativelanguage.googleapis.com" in base:
        return f"{base.rstrip('/')}/chat/completions"
    return f"{base}/v1/chat/completions"


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
    from src.jefrey.core.secret_store import read_secret
    return read_secret(_key_file())


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
        from src.jefrey.core.secret_store import write_secret
        kf = _key_file()
        if api_key.strip():
            write_secret(kf, api_key)  # protegida pelo Windows (DPAPI)
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


# Conexao reaproveitada entre as perguntas: abrir (e fechar) uma conexao segura nova a cada resposta custava
# de 0,2 a 0,6 s. Um cliente por laco de eventos; os testes (que passam `transport`) continuam com cliente proprio.
_pool: dict = {}


class _Borrowed:
    """Empresta o cliente compartilhado sem fecha-lo ao sair do `async with`."""

    def __init__(self, client: httpx.AsyncClient):
        self._c = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._c

    async def __aexit__(self, *exc) -> bool:
        return False


def _pooled() -> httpx.AsyncClient:
    import asyncio

    loop = asyncio.get_running_loop()
    c = _pool.get("client")
    if c is None or c.is_closed or _pool.get("loop") is not loop:
        c = httpx.AsyncClient(timeout=_timeout(), limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=90.0))
        _pool["client"], _pool["loop"] = c, loop
    return c


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
        except Exception as e:
            logger.debug("metrica de resposta nao registrada (%s)", type(e).__name__)

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
            return _chat_url(base), headers, body
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

    def _client(self):
        if self._transport is not None:  # testes: cliente proprio, com o transporte falso
            return httpx.AsyncClient(timeout=_timeout(), transport=self._transport)
        return _Borrowed(_pooled())

    # ---- chat completo ----------------------------------------------------------
    async def chat(self, messages: list[Message], role: Optional[str] = None) -> str:
        started = time.monotonic()
        url, headers, body = self._request(messages, stream=False)
        async with self._client() as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        text = self._extract_full(data)
        self._record(started, messages, text)
        return text

    async def describe_image(self, prompt: str, system: str, jpeg_b64: str) -> str:
        """Pergunta algo sobre uma imagem (JPEG em base64). Cerebro local (Ollama) nao ve: levanta LLMConfigError."""
        c = self.config
        if c.provider == "ollama":
            raise LLMConfigError("este cérebro local não vê imagens")
        url, headers, _ = self._request([{"role": "user", "content": "x"}], stream=False)
        if c.provider == "openai":
            body: dict[str, Any] = {
                "model": c.model, "stream": False, "max_tokens": 900, "temperature": 0.2,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": [{"type": "text", "text": prompt},
                                                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{jpeg_b64}"}}]}],
            }
        else:
            body = {
                "model": c.model, "max_tokens": 900, "temperature": 0.2, "system": system,
                "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": jpeg_b64}},
                                                          {"type": "text", "text": prompt}]}],
            }
        async with self._client() as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return self._extract_full(resp.json())

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
    async def stream(self, messages: list[Message], role: Optional[str] = None) -> AsyncIterator[str]:
        """Somente texto (sem ferramentas)."""
        async for item in self.stream_events(messages):
            if isinstance(item, str):
                yield item

    async def stream_events(self, messages: list[Message], tools: Optional[list[dict]] = None, role: Optional[str] = None) -> AsyncIterator[StreamItem]:
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
                    models_url = f"{base.rstrip('/')}/models" if "generativelanguage.googleapis.com" in base else f"{base}/v1/models"
                    r = await client.get(models_url,
                                         headers={"Authorization": f"Bearer {c.api_key}"} if c.api_key else {})
                    r.raise_for_status()
                    return {"ok": True, "provider": c.provider, "model": c.model, "detail": "conectado"}
                r = await client.get(f"{c.base_url}/v1/models",
                                     headers={"x-api-key": c.api_key or "", "anthropic-version": ANTHROPIC_VERSION})
                r.raise_for_status()
                return {"ok": True, "provider": c.provider, "model": c.model, "detail": "conectado"}
        except Exception as e:  # nunca incluir a chave na mensagem
            code = f" HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else ""
            return {"ok": False, "provider": c.provider, "model": c.model,
                    "detail": f"{type(e).__name__}: indisponivel{code}"}


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


# ---- reserva: se o provedor principal falhar, tenta o proximo ------------------------------
MAX_FALLBACKS = 9  # 1 principal + 9 = ate 10 cerebros conectados
COOLDOWN_S = 45.0
_RETRY_STATUS = {401, 402, 403, 404, 408, 409, 425, 429}  # 402 = sem credito: troca de cerebro em vez de falhar
LONG_COOLDOWN_S = 600.0  # sem credito ou chave recusada: nao adianta tentar de novo daqui a 45 s
LONG_COOLDOWN_STATUS = {401, 402, 403}


def _fallback_key_file(key_id: str) -> Path:
    return _config_dir() / "credentials" / f"llm_key_{key_id}"


def is_retryable(e: Exception) -> bool:
    """Falha que justifica tentar outro provedor (limite, queda, chave recusada, modelo ausente)."""
    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in _RETRY_STATUS or e.response.status_code >= 500
    return False


def load_fallback_entries() -> list[tuple[str, LLMConfig]]:
    """[(id do cerebro, configuracao)] das reservas validas, na ordem em que foram conectadas."""
    from src.jefrey.core.secret_store import read_secret

    out: list[tuple[str, LLMConfig]] = []
    for item in (load_override().get("fallbacks") or [])[:MAX_FALLBACKS]:
        if not isinstance(item, dict) or item.get("provider") not in PROVIDERS or not item.get("model"):
            continue
        provider = item["provider"]
        out.append((str(item.get("id", "")), LLMConfig(provider=provider, model=str(item["model"]),
                                                      base_url=_normalize_base(provider, str(item.get("base_url") or "")),
                                                      api_key=read_secret(_fallback_key_file(str(item.get("id", "")))) if item.get("id") else None)))
    return out


def load_fallback_configs() -> list[LLMConfig]:
    return [cfg for _, cfg in load_fallback_entries()]


# ---- funcoes de cada cerebro (quem faz o que) e trabalho em equipe ----
def load_roles() -> dict[str, list[str]]:
    """{id do cerebro: funcoes}. Cerebro sem registro serve para tudo; com lista vazia, so como reserva."""
    from src.jefrey.domain.llm_roles import clean_roles

    raw = load_override().get("roles")
    return {str(k): clean_roles(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def load_team() -> list[str]:
    from src.jefrey.domain.llm_roles import TEAM_ROLES, clean_roles

    return [r for r in clean_roles(load_override().get("team")) if r in TEAM_ROLES]


def _save_override_key(key: str, value: Any) -> None:
    data = load_override()
    data[key] = value
    _config_dir().mkdir(parents=True, exist_ok=True)
    _override_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_roles(brain_id: str, roles: Optional[list[str]]) -> None:
    """roles None apaga o registro (o cerebro volta a servir para tudo)."""
    from src.jefrey.domain.llm_roles import clean_roles

    cur = load_roles()
    if roles is None:
        cur.pop(brain_id, None)
    else:
        cur[brain_id] = clean_roles(roles)
    _save_override_key("roles", cur)


def save_team(roles: list[str]) -> None:
    from src.jefrey.domain.llm_roles import TEAM_ROLES, clean_roles

    _save_override_key("team", [r for r in clean_roles(roles) if r in TEAM_ROLES])


def save_fallbacks(items: list[dict]) -> None:
    """items: [{id, provider, model, base_url?, api_key?}]. api_key None mantem a atual; "" apaga."""
    from src.jefrey.core.secret_store import read_secret, valid_id

    if len(items) > MAX_FALLBACKS:
        raise LLMConfigError(f"no maximo {MAX_FALLBACKS} provedores de reserva")
    clean: list[dict] = []
    seen: set[str] = set()
    for it in items:
        kid, provider, model = str(it.get("id", "")), it.get("provider", ""), str(it.get("model", "")).strip()
        if not valid_id(kid) or kid in seen:
            raise LLMConfigError("identificador de reserva invalido ou repetido")
        if provider not in PROVIDERS or not model:
            raise LLMConfigError("reserva precisa de provedor valido e modelo")
        seen.add(kid)
        key = it.get("api_key")
        effective = read_secret(_fallback_key_file(kid)) if key is None else (str(key).strip() or None)
        LLMClient(LLMConfig(provider, model, _normalize_base(provider, str(it.get("base_url") or "")), api_key=effective))
        clean.append({"id": kid, "provider": provider, "model": model, "base_url": (str(it.get("base_url") or "").strip().rstrip("/") or None)})
    data = load_override()
    data["fallbacks"] = clean
    _config_dir().mkdir(parents=True, exist_ok=True)
    _override_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for it in items:
        kf = _fallback_key_file(str(it["id"]))
        if it.get("api_key") is not None:
            if str(it["api_key"]).strip():
                from src.jefrey.core.secret_store import write_secret as _w
                _w(kf, str(it["api_key"]))
            elif kf.exists():
                kf.unlink()
    for old in (_config_dir() / "credentials").glob("llm_key_*"):  # apaga chaves de reservas removidas
        if old.name[len("llm_key_"):] not in seen:
            old.unlink(missing_ok=True)


class RoutedLLM:
    """Mesma interface do LLMClient, com reserva. So troca de provedor ANTES de a resposta comecar."""

    def __init__(self, clients: list[LLMClient], clock=time.monotonic, roles: Optional[list] = None, team: tuple = ()):
        self.clients = clients
        self._clock = clock
        self._cool: dict[int, float] = {}
        self.last_label = ""
        self.last_index = 0
        self.roles: list = list(roles) if roles is not None else [None] * len(clients)  # funcoes de cada cerebro (None = serve para tudo)
        self.team = tuple(team)  # funcoes em que dois cerebros trabalham juntos (um escreve, outro revisa)

    @property
    def config(self) -> LLMConfig:
        return self.clients[0].config

    def _order(self, role: Optional[str] = None) -> list[int]:
        now = self._clock()
        ready = [i for i in range(len(self.clients)) if self._cool.get(i, 0) <= now]
        base = ready or [min(range(len(self.clients)), key=lambda i: self._cool.get(i, 0))]  # todos em espera: o que sai primeiro
        if role and any(r is not None for r in self.roles):
            from src.jefrey.domain.llm_roles import order_by_role

            return order_by_role(base, self.roles, role)
        return base

    async def stream_events(self, messages: list[Message], tools: Optional[list[dict]] = None, role: Optional[str] = None) -> AsyncIterator[StreamItem]:
        from src.jefrey.domain.llm_roles import effective_role

        last: Optional[Exception] = None
        for i in self._order(effective_role(role, messages, tools)):
            client, started = self.clients[i], False
            try:
                async for item in client.stream_events(messages, tools=tools):
                    started = True
                    self.last_index = i
                    self.last_label = f"{client.config.provider}:{client.config.model}"
                    yield item
                return
            except Exception as e:
                if started or not is_retryable(e):
                    raise  # ja respondeu algo (nao da para trocar) ou erro que outro provedor nao resolve
                last = e
                status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else 0
                self._cool[i] = self._clock() + (LONG_COOLDOWN_S if status in LONG_COOLDOWN_STATUS else COOLDOWN_S)
        if last is not None:
            raise last

    async def stream(self, messages: list[Message], role: Optional[str] = None) -> AsyncIterator[str]:
        async for item in self.stream_events(messages, role=role):
            if isinstance(item, str):
                yield item

    async def chat(self, messages: list[Message], role: Optional[str] = None) -> str:
        draft = "".join([t async for t in self.stream(messages, role=role)])
        if role in self.team and draft.strip():
            return await self._review(messages, draft, role)
        return draft

    async def describe_image(self, prompt: str, system: str, jpeg_b64: str) -> str:
        """Tenta os cerebros que veem imagens (funcao "visao" primeiro) ate um responder."""
        last: Optional[Exception] = None
        for i in self._order("visao"):
            try:
                out = await self.clients[i].describe_image(prompt, system, jpeg_b64)
            except Exception as e:
                last = e
                if is_retryable(e):
                    self._cool[i] = self._clock() + COOLDOWN_S
                continue
            if out.strip():
                return out
        if last is not None:
            raise last
        return ""

    async def _review(self, messages: list[Message], draft: str, role: str) -> str:
        """Trabalho em equipe: outro cerebro com a mesma funcao revisa o rascunho. Qualquer falha devolve o rascunho (nunca piora)."""
        from src.jefrey.domain.llm_roles import review_messages

        others = [i for i in self._order(role) if i != self.last_index and self.roles[i] is not None and role in self.roles[i]]
        if not others:
            return draft
        try:
            better = await self.clients[others[0]].chat(review_messages(messages, draft))
        except Exception as e:
            logger.info("revisao em equipe falhou (%s): fica o rascunho", type(e).__name__)
            return draft
        return better.strip() or draft

    async def health(self) -> dict:
        return await self.clients[0].health()


def get_llm_client() -> "LLMClient | RoutedLLM":
    from src.jefrey.domain.llm_roles import ROLES  # noqa: F401

    primary = LLMClient(config_from_settings())
    extra: list[LLMClient] = []
    ids: list[str] = [_primary_id(primary.config)]
    for bid, cfg in load_fallback_entries():
        try:
            extra.append(LLMClient(cfg))
            ids.append(bid)
        except LLMConfigError:
            continue  # reserva mal configurada nao derruba o principal
    if not extra:
        return primary
    roles_map = load_roles()
    roles = [set(roles_map[i]) if i in roles_map else None for i in ids]
    return RoutedLLM([primary, *extra], roles=roles, team=tuple(load_team()))


def _primary_id(cfg: LLMConfig) -> str:
    from src.jefrey.adapters.outbound.brains import identify

    return identify(cfg.provider, cfg.base_url)

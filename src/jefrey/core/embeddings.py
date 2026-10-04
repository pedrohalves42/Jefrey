"""Embeddings (busca por sentido) sem depender de um unico servico.

Ordem de escolha no modo nativo (a PRIMEIRA que funcionar e gravada e nunca muda sozinha, porque vetores de
modelos diferentes nao se misturam e trocar no meio dividiria as memorias em duas colecoes):
  1. Ollama local (embeddinggemma)           -> privado, melhor em portugues entre os locais que medimos
  2. API compativel com OpenAI da nuvem do usuario (OpenRouter: baai/bge-m3; OpenAI: text-embedding-3-small)
  3. Motor local embutido do Chroma (ONNX)   -> sem servico externo; qualidade menor em portugues
Sem nenhuma opcao a memoria fica INDISPONIVEL com mensagem clara (o chat segue sem ela), nunca erro 500.
No modo Docker/servidor vale a configuracao fixa (sem escolha automatica).
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "embeddinggemma"
OPENROUTER_MODEL = "baai/bge-m3"
OPENAI_MODEL = "text-embedding-3-small"
CHROMA_MODEL = "all-MiniLM-L6-v2"
BATCH = 32
UNAVAILABLE_MSG = ("A memória precisa de um serviço de busca por sentido: o Ollama no seu computador ou uma chave de nuvem "
                   "(OpenRouter ou OpenAI). Conecte um em Configurações.")


class EmbeddingsUnavailable(RuntimeError):
    """Nenhum backend de embeddings esta funcionando. A mensagem e segura para mostrar ao usuario."""


@dataclass(frozen=True)
class Choice:
    backend: str  # ollama | openai | chroma
    model: str
    base_url: str = ""

    @property
    def model_id(self) -> str:
        """Identificador do espaco vetorial (nome da colecao). ollama mantem o nome do modelo (preserva dados antigos)."""
        if self.backend == "ollama":
            return self.model
        if self.backend == "chroma":
            return "chroma-default"
        host = re.sub(r"^https?://", "", self.base_url).split("/")[0].split(".")[-2] if "." in self.base_url else "openai"
        return f"{host}-{self.model}"


# ---------------------------------------------------------------- backends
class HttpEmbeddings:
    """Ollama (/api/embed) ou API compativel com OpenAI (/v1/embeddings). Sincrono, com lotes."""

    def __init__(self, choice: Choice, api_key: Optional[str] = None, transport: Optional[httpx.BaseTransport] = None,
                 timeout: float = 60.0):
        if choice.backend not in ("ollama", "openai"):
            raise ValueError("backend http invalido")
        self.choice, self._key, self._transport, self._timeout = choice, api_key, transport, timeout

    @property
    def model_id(self) -> str:
        return self.choice.model_id

    def _post(self, texts: list[str]) -> list[list[float]]:
        c = self.choice
        base = c.base_url.rstrip("/")
        base = base[:-3] if base.endswith("/v1") else base
        if c.backend == "ollama":
            url, headers, body = f"{base}/api/embed", {}, {"model": c.model, "input": texts}
        else:
            url, headers = f"{base}/v1/embeddings", {"Authorization": f"Bearer {self._key}"} if self._key else {}
            body = {"model": c.model, "input": texts}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                r = client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            why = "chave recusada" if code in (401, 403) else "modelo de embeddings nao encontrado" if code == 404 else \
                "limite de uso atingido" if code == 429 else f"HTTP {code}"
            raise EmbeddingsUnavailable(f"Busca por sentido indisponível ({why}).") from None
        except (httpx.HTTPError, ValueError) as e:  # nunca inclui URL com chave nem o texto
            raise EmbeddingsUnavailable(f"Busca por sentido indisponível ({type(e).__name__}).") from None
        try:
            if c.backend == "ollama":
                vecs = data["embeddings"]
            else:
                vecs = [d["embedding"] for d in sorted(data["data"], key=lambda d: d.get("index", 0))]
        except (KeyError, TypeError):
            raise EmbeddingsUnavailable("Busca por sentido indisponível (resposta inesperada).") from None
        if len(vecs) != len(texts) or any(not v for v in vecs):
            raise EmbeddingsUnavailable("Busca por sentido indisponível (resposta incompleta).")
        return [[float(x) for x in v] for v in vecs]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            out.extend(self._post(texts[i:i + BATCH]))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._post([text])[0]


class ChromaDefaultEmbeddings:
    """Motor local embutido do Chroma (ONNX). Baixa o modelo (~80 MB) na primeira vez e depois funciona offline."""

    choice = Choice("chroma", CHROMA_MODEL)

    def __init__(self, factory: Optional[Callable[[], Any]] = None):
        self._factory, self._fn = factory, None

    @property
    def model_id(self) -> str:
        return self.choice.model_id

    def _ef(self):
        if self._fn is None:
            try:
                if self._factory:
                    self._fn = self._factory()
                else:
                    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
                    self._fn = DefaultEmbeddingFunction()
            except Exception as e:
                raise EmbeddingsUnavailable(f"Busca por sentido indisponível ({type(e).__name__}).") from None
        return self._fn

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return [[float(x) for x in v] for v in self._ef()(texts)]
        except EmbeddingsUnavailable:
            raise
        except Exception as e:
            raise EmbeddingsUnavailable(f"Busca por sentido indisponível ({type(e).__name__}).") from None

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# ---------------------------------------------------------------- escolha automatica e persistencia
def _choice_file() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "embeddings.runtime.json"


def load_choice() -> Optional[Choice]:
    try:
        d = json.loads(_choice_file().read_text(encoding="utf-8"))
        if d.get("backend") in ("ollama", "openai", "chroma") and d.get("model"):
            return Choice(d["backend"], str(d["model"]), str(d.get("base_url") or ""))
    except (OSError, ValueError, AttributeError):
        pass
    return None


def save_choice(c: Choice) -> None:
    f = _choice_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"backend": c.backend, "model": c.model, "base_url": c.base_url}), encoding="utf-8")
    os.replace(tmp, f)


def forget_choice() -> None:
    _choice_file().unlink(missing_ok=True)


def cloud_choice(base_url: str, api_key: Optional[str]) -> Optional[Choice]:
    """Embeddings pela mesma nuvem do chat, quando ela tem o servico (OpenRouter, OpenAI). Anthropic nao tem."""
    if not api_key or not base_url:
        return None
    b = base_url.lower()
    if "openrouter.ai" in b:
        return Choice("openai", OPENROUTER_MODEL, base_url.rstrip("/"))
    if "api.openai.com" in b:
        return Choice("openai", OPENAI_MODEL, base_url.rstrip("/"))
    return None


def build_backend(choice: Choice, api_key: Optional[str]):
    return ChromaDefaultEmbeddings() if choice.backend == "chroma" else HttpEmbeddings(choice, api_key)


class AutoEmbeddings:
    """Resolve o backend na primeira necessidade. `candidates` devolve [(Choice, api_key)] em ordem de preferencia."""

    def __init__(self, candidates: Callable[[], list[tuple[Choice, Optional[str]]]], auto: bool = True,
                 builder: Callable[[Choice, Optional[str]], Any] = build_backend):
        self._candidates, self._auto, self._builder = candidates, auto, builder
        self._impl: Any = None

    def reset(self) -> None:
        self._impl = None

    def _probe(self, impl: Any) -> None:
        v = impl.embed_query("teste de conexao")
        if not v or len(v) < 8:
            raise EmbeddingsUnavailable("Busca por sentido indisponível (vetor invalido).")

    def resolve(self):
        if self._impl is not None:
            return self._impl
        cands = self._candidates()
        saved = load_choice() if self._auto else None
        if saved is not None:
            # escolha ja feita: nunca troca sozinho (misturaria espacos vetoriais); so refaz a conexao
            key = next((k for c, k in cands if c.backend == saved.backend and c.model == saved.model), None)
            if key is None and saved.backend == "openai":
                from src.jefrey.core.llm_provider import load_saved_key
                key = load_saved_key() or os.getenv("JEFREY_LLM__API_KEY")
            impl = self._builder(saved, key)
            self._probe(impl)
            self._impl = impl
            return impl
        last: Optional[Exception] = None
        for choice, key in cands:
            try:
                impl = self._builder(choice, key)
                self._probe(impl)
            except EmbeddingsUnavailable as e:
                last = e
                logger.info("embeddings: %s/%s indisponivel", choice.backend, choice.model)
                continue
            if self._auto:
                save_choice(choice)
            self._impl = impl
            logger.info("embeddings: usando %s/%s", choice.backend, choice.model)
            return impl
        raise EmbeddingsUnavailable(UNAVAILABLE_MSG) from last

    @property
    def model_id(self) -> str:
        return self.resolve().model_id

    def embed_query(self, text: str) -> list[float]:
        return self.resolve().embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.resolve().embed_documents(texts)


def default_candidates() -> list[tuple[Choice, Optional[str]]]:
    """Candidatos conforme o modo. Modo servidor/Docker: so a configuracao fixa."""
    from src.jefrey.core.config import get_settings
    from src.jefrey.core.llm_provider import config_from_settings, load_saved_key
    from src.jefrey.core.redis_factory import is_native

    s = get_settings().embeddings
    llm_key = load_saved_key() or os.getenv("JEFREY_LLM__API_KEY")
    if not is_native():
        if s.provider == "ollama":
            return [(Choice("ollama", s.model, s.base_url), None)]
        return [(Choice("openai", s.model, s.base_url or "https://api.openai.com"), s.api_key or llm_key)]
    out: list[tuple[Choice, Optional[str]]] = [(Choice("ollama", OLLAMA_MODEL, s.base_url), None)]
    try:
        cfg = config_from_settings()
        cc = cloud_choice(cfg.base_url, cfg.api_key or llm_key) if cfg.provider == "openai" else None
        if cc:
            out.append((cc, cfg.api_key or llm_key))
    except Exception as _e:
        logger.debug("ignorado (%s): %s", 'embeddings.py', type(_e).__name__)
    out.append((Choice("chroma", CHROMA_MODEL), None))
    return out

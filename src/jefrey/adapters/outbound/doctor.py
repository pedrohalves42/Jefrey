"""`jefrey doctor`: diagnostica o ambiente e diz COMO resolver cada problema.

Tudo que toca o mundo externo entra por `Probes`, entao os testes controlam cada resposta.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import httpx

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    status: str  # ok | warn | fail
    detail: str
    fix: str = ""


@dataclass
class Probes:
    base_url: str = "http://localhost:8000"
    ollama_url: str = "http://localhost:11434"
    project_dir: Path = field(default_factory=Path.cwd)
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    python_version: tuple[int, int] = field(default_factory=lambda: sys.version_info[:2])
    http_get: Optional[Callable[[str], tuple[int, Any]]] = None
    memory_gb: Optional[Callable[[], tuple[float, float]]] = None
    disk_free_gb: Optional[Callable[[Path], float]] = None
    chat_model: Optional[Callable[[], tuple[str, str]]] = None  # (provedor, modelo)
    embed_model: Optional[Callable[[], str]] = None

    def get(self, url: str) -> tuple[int, Any]:
        """(status, json|None). Status 0 = sem conexao."""
        if self.http_get:
            return self.http_get(url)
        try:
            r = httpx.get(url, timeout=5)
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, None
        except httpx.HTTPError:
            return 0, None

    def mem(self) -> tuple[float, float]:
        if self.memory_gb:
            return self.memory_gb()
        from src.jefrey.core.hardware import read_memory_gb
        return read_memory_gb()

    def disk(self, path: Path) -> float:
        if self.disk_free_gb:
            return self.disk_free_gb(path)
        return shutil.disk_usage(path).free / 2**30

    def chat(self) -> tuple[str, str]:
        if self.chat_model:
            return self.chat_model()
        from src.jefrey.core.llm_provider import config_from_settings
        c = config_from_settings()
        return c.provider, c.model

    def embed(self) -> str:
        if self.embed_model:
            return self.embed_model()
        from src.jefrey.core.config import get_settings
        return get_settings().embeddings.model


def _model_installed(names: list[str], wanted: str) -> bool:
    base = wanted.split(":")[0]
    return any(n == wanted or (":" not in wanted and n.split(":")[0] == base) for n in names)


def run_checks(p: Optional[Probes] = None) -> list[Check]:
    p = p or Probes()
    out: list[Check] = []
    add = out.append

    # ---- Python ----
    major, minor = p.python_version
    if (major, minor) >= (3, 12):
        add(Check("python", "Python", OK, f"{major}.{minor}"))
    elif (major, minor) >= (3, 11):
        add(Check("python", "Python", WARN, f"{major}.{minor} (recomendado 3.12)", "Instale o Python 3.12 em python.org."))
    else:
        add(Check("python", "Python", FAIL, f"{major}.{minor} e antigo demais", "Instale o Python 3.12 em python.org."))

    # ---- servidor ----
    status, _ = p.get(f"{p.base_url}/health")
    api_up = status == 200
    add(Check("api", "Servidor do Jefrey", OK if api_up else FAIL,
              f"respondendo em {p.base_url}" if api_up else (f"respondeu HTTP {status}" if status else "nao respondeu"),
              "" if api_up else "Abra o Docker Desktop e rode: docker compose up -d   (ou de duplo clique em start_jefrey.bat)."))

    # ---- servicos internos ----
    if api_up:
        st, body = p.get(f"{p.base_url}/api/status")
        if st == 200 and isinstance(body, dict):
            names = {"postgres": "Banco de dados", "redis": "Cache", "ollama": "Modelo local (Ollama)",
                     "mcp": "Ferramentas (MCP)", "stt": "Voz para texto", "tts": "Texto para voz"}
            essential = {"postgres", "redis", "ollama"}
            for key, label in names.items():
                s = (body.get(key) or {}).get("status") if isinstance(body.get(key), dict) else None
                if s == "off":
                    continue  # nao faz parte deste modo (ex.: Redis/MCP no modo nativo)
                if s == "ok":
                    add(Check(key, label, OK, "ok"))
                else:
                    add(Check(key, label, FAIL if key in essential else WARN, "fora do ar",
                              f"Reinicie o servico: docker compose restart {'mcp-server' if key == 'mcp' else key}"))
        else:
            add(Check("services", "Servicos internos", WARN, "nao consegui consultar /api/status"))

    # ---- modelos no Ollama ----
    st, tags = p.get(f"{p.ollama_url}/api/tags")
    if st != 200 or not isinstance(tags, dict):
        provider, model = p.chat()
        if provider == "ollama":
            add(Check("models", "Modelos locais", FAIL, f"nao consegui falar com o Ollama em {p.ollama_url}",
                      "Confirme que o container 'jefrey-ollama' esta rodando (docker ps)."))
    else:
        installed = [m.get("name", "") for m in tags.get("models", []) if isinstance(m, dict)]
        provider, model = p.chat()
        if provider != "ollama":
            add(Check("chat_model", "Modelo de conversa", OK, f"{model} via {provider} (nuvem)"))
        elif _model_installed(installed, model):
            add(Check("chat_model", "Modelo de conversa", OK, f"{model} instalado"))
        else:
            add(Check("chat_model", "Modelo de conversa", FAIL, f"{model} nao esta instalado",
                      f"docker exec jefrey-ollama ollama pull {model}"))
        emb = p.embed()
        if _model_installed(installed, emb):
            add(Check("embed_model", "Modelo de memoria", OK, f"{emb} instalado"))
        else:
            add(Check("embed_model", "Modelo de memoria", FAIL, f"{emb} nao esta instalado (a memoria nao funciona sem ele)",
                      f"docker exec jefrey-ollama ollama pull {emb}"))

    # ---- memoria RAM e disco ----
    total, avail = p.mem()
    if total > 0:
        if avail < 1.0:
            add(Check("ram", "Memoria RAM livre", FAIL, f"{avail:.1f} GB livres de {total:.1f} GB",
                      "Feche programas pesados. Se usa o Docker, pare o que nao precisa: docker stop jefrey-grafana jefrey-prometheus jefrey-n8n jefrey-mcp jefrey-frontend jefrey-brain2 (o modo leve ja sobe sem eles)"))
        elif avail < 2.5:
            add(Check("ram", "Memoria RAM livre", WARN, f"{avail:.1f} GB livres de {total:.1f} GB (respostas podem ficar lentas)",
                      "Use o modelo leve qwen3:1.7b e feche outros programas."))
        else:
            add(Check("ram", "Memoria RAM livre", OK, f"{avail:.1f} GB livres de {total:.1f} GB"))
    free = p.disk(p.project_dir)
    if free < 1.0:
        add(Check("disk", "Espaco em disco", FAIL, f"{free:.1f} GB livres (o Docker trava sem espaco)",
                  "Libere espaco: docker builder prune -f   e apague modelos que nao usa (ollama rm <modelo>)."))
    elif free < 5.0:
        add(Check("disk", "Espaco em disco", WARN, f"{free:.1f} GB livres", "Considere liberar espaco: docker builder prune -f"))
    else:
        add(Check("disk", "Espaco em disco", OK, f"{free:.1f} GB livres"))

    # ---- segredos ----
    env_file = p.project_dir / ".env"
    if not env_file.exists():
        add(Check("env", "Arquivo .env", FAIL, "nao existe", "Copie .env.example para .env e preencha os segredos."))
    else:
        secret = p.env.get("JEFREY_API__SECRET_KEY", "")
        if not secret:
            for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("JEFREY_API__SECRET_KEY="):
                    secret = line.split("=", 1)[1].strip().strip('"')
        if len(secret) < 32 or "CHANGE_ME" in secret.upper():
            add(Check("secret", "Chave secreta da API", FAIL, "ausente, curta ou ainda e o valor de exemplo",
                      "Gere uma: python -c \"import secrets; print(secrets.token_hex(32))\" e ponha em JEFREY_API__SECRET_KEY."))
        else:
            add(Check("secret", "Chave secreta da API", OK, "definida"))

    # ---- WhatsApp (opcional) ----
    if (p.env.get("JEFREY_WHATSAPP__ENABLED") or "").lower() in ("1", "true", "yes"):
        from src.jefrey.channels.whatsapp import WhatsAppConfig
        cfg = WhatsAppConfig.from_env(p.env)
        missing = [k for k, v in (("VERIFY_TOKEN", cfg.verify_token), ("APP_SECRET", cfg.app_secret),
                                  ("ALLOWED", cfg.allowed), ("ACCESS_TOKEN", cfg.access_token),
                                  ("PHONE_NUMBER_ID", cfg.phone_number_id)) if not v]
        if missing:
            add(Check("whatsapp", "WhatsApp", FAIL, "ligado, mas faltam: " + ", ".join(missing),
                      "Preencha as variaveis JEFREY_WHATSAPP__* (veja docs/WHATSAPP.md)."))
        else:
            add(Check("whatsapp", "WhatsApp", OK, f"configurado para {len(cfg.allowed)} numero(s)"))
    return out


def summarize(checks: list[Check]) -> tuple[int, int, int]:
    return (sum(c.status == OK for c in checks), sum(c.status == WARN for c in checks), sum(c.status == FAIL for c in checks))

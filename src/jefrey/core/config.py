"""Configuracao centralizada com Pydantic Settings v2."""
from __future__ import annotations
import threading
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_LLM__", extra="ignore")
    
    provider: Literal["openai", "anthropic", "ollama"] = "ollama"
    model: str = "llama3.1:8b"
    temperature: float = 0.7
    max_tokens: int = 4000
    base_url: Optional[str] = "http://localhost:11434"
    api_key: Optional[str] = None
    
    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, v: Optional[str]) -> Optional[str]:
        """Remove /v1 do final se presente - o cliente adiciona automaticamente."""
        if v:
            v = v.rstrip("/")
            if v.endswith("/v1"):
                v = v[:-3]
        return v

class EmbeddingsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_EMBEDDINGS__", extra="ignore")
    
    model: str = "nomic-embed-text"
    base_url: str = "http://localhost:11434"
    api_key: str = ""

class MemoryShortTermSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_MEMORY__SHORT_TERM__", extra="ignore")
    
    max_messages: int = 20
    max_tokens: int = 8000

class MemoryLongTermSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_MEMORY__LONG_TERM__", extra="ignore")
    
    provider: Literal["chromadb", "sqlite-vec", "postgres", "postgresql"] = "chromadb"
    persist_directory: str = "data/chroma_db"
    collection_name: str = "jefrey_memory"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768  # nomic-embed-text via Ollama = 768 dims (1536 quebra pgvector)
    top_k: int = 5
    similarity_threshold: float = 0.7

class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_MEMORY__", extra="ignore")
    
    short_term: MemoryShortTermSettings = MemoryShortTermSettings()
    long_term: MemoryLongTermSettings = MemoryLongTermSettings()

class VoiceWakeWordSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_VOICE__WAKE_WORD__", extra="ignore")
    
    enabled: bool = False
    provider: Literal["porcupine", "openwakeword"] = "porcupine"
    access_key: str = ""
    keywords: list[str] = ["jefrey"]

class VoiceSTTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_VOICE__STT__", extra="ignore")
    
    provider: Literal["whisper", "google", "azure"] = "whisper"
    model: str = "base"
    language: str = "pt"

class VoiceTTSSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_VOICE__TTS__", extra="ignore")
    
    provider: Literal["piper", "elevenlabs", "pyttsx3"] = "piper"
    voice: str = "pt_BR-faber-medium"
    speed: float = 1.0

class VoiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_VOICE__", extra="ignore")
    
    enabled: bool = False
    wake_word: VoiceWakeWordSettings = VoiceWakeWordSettings()
    stt: VoiceSTTSettings = VoiceSTTSettings()
    tts: VoiceTTSSettings = VoiceTTSSettings()

class GoogleCalendarSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_INTEGRATIONS__GOOGLE_CALENDAR__", extra="ignore")
    
    enabled: bool = False
    credentials_file: str = "config/credentials/google_calendar.json"
    token_file: str = "config/tokens/google_calendar_token.json"

class GmailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_INTEGRATIONS__GMAIL__", extra="ignore")
    
    enabled: bool = False
    credentials_file: str = "config/credentials/gmail.json"
    token_file: str = "config/tokens/gmail_token.json"

class GoogleDriveSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_INTEGRATIONS__GOOGLE_DRIVE__", extra="ignore")
    
    enabled: bool = False
    credentials_file: str = "config/credentials/google_drive.json"
    token_file: str = "config/tokens/google_drive_token.json"

class NotionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_INTEGRATIONS__NOTION__", extra="ignore")
    
    enabled: bool = False
    token: str = ""

class ComposioSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_INTEGRATIONS__COMPOSIO__", extra="ignore")
    
    enabled: bool = False
    api_key: str = ""

class IntegrationsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_INTEGRATIONS__", extra="ignore")
    
    google_calendar: GoogleCalendarSettings = GoogleCalendarSettings()
    gmail: GmailSettings = GmailSettings()
    google_drive: GoogleDriveSettings = GoogleDriveSettings()
    notion: NotionSettings = NotionSettings()
    composio: ComposioSettings = ComposioSettings()

class SkillsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_SKILLS__", extra="ignore")
    
    calendar: bool = True
    email: bool = True
    web_search: bool = True
    notes: bool = True
    automation: bool = True
    drive: bool = True
    weather: bool = False
    stocks: bool = False

class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_LOGGING__", extra="ignore")
    
    level: str = "INFO"
    file: str = "logs/jefrey.log"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_DATABASE__", extra="ignore")

    url: Optional[str] = None
    host: str = "localhost"
    port: int = 5432
    user: str = "jefrey"
    # SECURITY NOTE: password default e 'jefrey' para DEV. Em producao, via env var.
    # Senha obrigatoria — definir via JEFREY_DATABASE__PASSWORD no .env.
    # Sem ela, o middleware de auth recusa todas as requests (CIPHER-018/025).
    password: str = Field(default="", alias="JEFREY_DATABASE__PASSWORD")
    db: str = "jefrey"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    @property
    def dsn(self) -> str:
        if self.url:
            return self.url
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_REDIS__", extra="ignore")

    url: Optional[str] = None
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 50

    @property
    def dsn(self) -> str:
        if self.url:
            return self.url
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

class PolicySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_POLICY__", extra="ignore")

    mode: Literal["enforce", "audit", "off"] = "enforce"
    autonomous: bool = True
    rate_limit_max: int = Field(default=20, ge=1, le=10000)
    rate_limit_window: float = Field(default=60.0, gt=0, le=86400)

class HITLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_HITL__", extra="ignore")

    # RISCO ATIVO (P4): prazo maximo de uma aprovacao pendente. Apos expirar, a
    # aprovacao transiciona para 'expired' e a ferramenta e negada (o agent loop
    # nao pode travar para sempre aguardando o humano). Padrao: 30 minutos.
    approval_ttl: float = 1800.0
    poll_interval: float = 2.0

class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_API__", extra="ignore")

    # CIPHER-019: segredo do Bearer token que protege os endpoints HITL de aprovacao
    # (api/approvals.py). OBRIGATORIO em producao: se vazio, o middleware de auth recusa
    # TODAS as requests (nenhum token valido e possivel) -> o endpoint NUNCA sobe sem
    # autenticacao. Gere com `python -c "import secrets; print(secrets.token_hex(32))"`.
    secret_key: str = ""

    # CIPHER-025: caminho de fallback local para o trilho de auditoria quando o
    # Postgres esta fora (dual-write). Garante rastro forense mesmo em queda.
    audit_fallback_path: str = "data/audit_fallback.jsonl"

    def validate_for_production(self) -> list[str]:
        """Valida configuracoes obrigatorias para producao. Retorna lista de warnings."""
        warnings = []
        if not self.secret_key:
            warnings.append(
                "JEFREY_API__SECRET_KEY esta vazio! "
                "Nenhum Bearer token sera aceito. "
                "Gere com: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return warnings

class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_AGENT__", extra="ignore")

    provider: Literal["langgraph", "openai"] = "langgraph"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    system_prompt: str = "Voce e o Jefrey, um assistente pessoal avancado e prestativo."

class MCPServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JEFREY_MCP__", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8001
    transport: str = "streamable-http"
    path: str = "/mcp"
    # JSON-response mode (P3b): o servidor responde JSON-RPC puro (sem SSE) quando o
    # cliente envia Accept: application/json. Mantem retrocompatibilidade com o cliente
    # mcp (verify_p3a) que envia 'application/json, text/event-stream' e aceita ambos os
    # formatos. Habilitado por padrao para o n8n chamar via HTTP Request nodes de forma
    # deterministica (sem parse de Server-Sent Events).
    json_response: bool = True
    # Stateless HTTP (P3b): cada requisicao MCP cria um transporte/server fresco, sem
    # rastreamento de sessao (sem obrigatoriedade do header Mcp-Session-Id nem do
    # handshake stateful). Isso elimina a fiacao de sessao que quebrava o n8n (o Code
    # node do n8n nao tem fetch/require e o HTTP Request node nao expunha o session id).
    # Com stateless, o n8n faz um unico POST tools/call e recebe o resultado. Clientes
    # MCP completos (verify_p3a/openai-agents) tambem funcionam: initialize+tools/call
    # sao aceitos em modo stateless.
    stateless_http: bool = True

    # CIPHER-001: papel efetivo resolvido SERVER-SIDE (nunca vem do caller/MCP payload).
    # service_role e a fonte de verdade em producao ("user"). "admin" NUNCA deve ser o
    # default -- apenas em implantacoes internas confiaveis, validado via allowed_roles.
    service_role: str = "user"
    allowed_roles: list[str] = ["user"]
    # CIPHER-018: timeout (segundos) aplicado a cada tool.ainvoke.
    tool_timeout: float = 30.0

class ExternalMCPServer(BaseSettings):
    """Spec de um servidor MCP externo que o Jefrey consome via MCPClient (P3c)."""

    model_config = SettingsConfigDict(extra="ignore")

    name: str = "external"
    url: str = ""          # streamable-http (ex.: http://n8n:5678/mcp/...)
    command: str = ""      # stdio: "python scripts/mcp_external_demo_server.py"
    transport: str = "streamable-http"  # "streamable-http" | "stdio"
    env: dict = {}         # env extra apenas para stdio

class MCPClientSettings(BaseSettings):
    """Config do MCPClient isolado (P3c). O agent loop o consome em P4."""

    model_config = SettingsConfigDict(env_prefix="JEFREY_MCP_CLIENT__", extra="ignore")

    enabled: bool = False
    # Lista de servidores externos (env nested: JEFREY_MCP_CLIENT__SERVERS__0__URL=...)
    servers: list[ExternalMCPServer] = []

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_prefix="JEFREY_",
        extra="ignore",
    )

    # FASE 0 — JEFREY_ENV enum fail-closed (Axiom #6, Security Eng ch.4)
    # dev = permissivo (auto-key warn ok), prod = fail-closed (RuntimeError se secret ausente)
    # Reproducao C1a: JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY= python -c "from src.jefrey.eventbus.signing import _get_hmac_key; _get_hmac_key()" -> RuntimeError
    env: Literal["dev", "prod"] = Field(default="dev", validation_alias="JEFREY_ENV")
    name: str = "Jefrey"
    version: str = "0.1.0"
    user_name: str = "Usuario"
    debug: bool = Field(default=False, validation_alias="JEFREY_DEBUG")

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    def validate_for_production(self) -> list[str]:
        """FASE 0 — valida segredos obrigatorios quando JEFREY_ENV=prod (fail-closed, Axiom #6)."""
        warnings: list[str] = []
        warnings.extend(self.api.validate_for_production())
        if self.is_prod:
            import os
            hmac_key = os.getenv("JEFREY_EVENTBUS__HMAC_KEY", "")
            if not hmac_key or len(hmac_key) < 32:
                warnings.append("JEFREY_EVENTBUS__HMAC_KEY ausente ou <32 chars em prod (C1a) — deve dar RuntimeError, nao warn")
            for k in ["JEFREY_OAUTH__CLIENT_ID", "JEFREY_OAUTH__TOKEN_URI", "JEFREY_OAUTH__AUD", "JEFREY_OAUTH__ISS"]:
                if not os.getenv(k):
                    warnings.append(f"{k} ausente em prod (A6) — OAuth sem AUD/ISS aceita token de outro issuer")
            if not os.getenv("JEFREY_REDIS__PASSWORD"):
                warnings.append("JEFREY_REDIS__PASSWORD vazio em prod (A6)")
            if self.api.secret_key and "CHANGE_ME" in self.api.secret_key:
                warnings.append("JEFREY_API__SECRET_KEY ainda CHANGE_ME em prod")
        return warnings
    
    llm: LLMSettings = LLMSettings()
    memory: MemorySettings = MemorySettings()
    embeddings: EmbeddingsSettings = EmbeddingsSettings()
    voice: VoiceSettings = VoiceSettings()
    integrations: IntegrationsSettings = IntegrationsSettings()
    skills: SkillsSettings = SkillsSettings()
    logging: LoggingSettings = LoggingSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    agent: AgentSettings = AgentSettings()
    policy: PolicySettings = PolicySettings()
    hitl: HITLSettings = HITLSettings()
    api: APISettings = APISettings()
    mcp: MCPServerSettings = MCPServerSettings()
    mcp_client: MCPClientSettings = MCPClientSettings()

# Instancia global (lazy) -- thread-safe
_settings: AppSettings | None = None
_settings_lock = threading.Lock()

def get_settings() -> AppSettings:
    """Retorna instancia singleton de configuracoes (thread-safe)."""
    global _settings
    if _settings is None:
        with _settings_lock:
            if _settings is None:
                _settings = AppSettings()
    return _settings

def reload_settings() -> AppSettings:
    """Forca recarregamento das configuracoes."""
    global _settings
    with _settings_lock:
        _settings = AppSettings()
    return _settings

# Para compatibilidade
settings = get_settings()

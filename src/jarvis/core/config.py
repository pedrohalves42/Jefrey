"""Configuração centralizada com Pydantic Settings."""
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class LLMSettings(BaseSettings):
    provider: Literal["openai", "ollama", "anthropic"] = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4000
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class MemoryShortTermSettings(BaseSettings):
    max_messages: int = 20
    max_tokens: int = 8000


class MemoryLongTermSettings(BaseSettings):
    provider: Literal["chromadb", "sqlite-vec"] = "chromadb"
    persist_directory: str = "data/chroma_db"
    collection_name: str = "jarvis_memory"
    embedding_model: str = "text-embedding-3-small"
    top_k: int = 5
    similarity_threshold: float = 0.7


class MemorySettings(BaseSettings):
    short_term: MemoryShortTermSettings = MemoryShortTermSettings()
    long_term: MemoryLongTermSettings = MemoryLongTermSettings()


class VoiceWakeWordSettings(BaseSettings):
    enabled: bool = False
    provider: Literal["porcupine", "openwakeword"] = "porcupine"
    access_key: str = ""
    keywords: list[str] = ["jarvis"]


class VoiceSTTSettings(BaseSettings):
    provider: Literal["whisper", "google", "azure"] = "whisper"
    model: str = "base"
    language: str = "pt"


class VoiceTTSSettings(BaseSettings):
    provider: Literal["piper", "elevenlabs", "pyttsx3"] = "piper"
    voice: str = "pt_BR-faber-medium"
    speed: float = 1.0


class VoiceSettings(BaseSettings):
    enabled: bool = False
    wake_word: VoiceWakeWordSettings = VoiceWakeWordSettings()
    stt: VoiceSTTSettings = VoiceSTTSettings()
    tts: VoiceTTSSettings = VoiceTTSSettings()


class GoogleCalendarSettings(BaseSettings):
    enabled: bool = False
    credentials_file: str = "config/credentials/google_calendar.json"
    token_file: str = "config/tokens/google_calendar_token.json"


class GmailSettings(BaseSettings):
    enabled: bool = False
    credentials_file: str = "config/credentials/gmail.json"
    token_file: str = "config/tokens/gmail_token.json"


class NotionSettings(BaseSettings):
    enabled: bool = False


class ComposioSettings(BaseSettings):
    enabled: bool = False


class IntegrationsSettings(BaseSettings):
    google_calendar: GoogleCalendarSettings = GoogleCalendarSettings()
    gmail: GmailSettings = GmailSettings()
    notion: NotionSettings = NotionSettings()
    composio: ComposioSettings = ComposioSettings()


class SkillsSettings(BaseSettings):
    calendar: bool = True
    email: bool = True
    web_search: bool = True
    notes: bool = True
    automation: bool = True
    weather: bool = False
    stocks: bool = False


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    file: str = "logs/jarvis.log"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    name: str = "Jefrey"
    version: str = "0.1.0"
    user_name: str = "Usuário"
    debug: bool = True

    llm: LLMSettings = LLMSettings()
    memory: MemorySettings = MemorySettings()
    voice: VoiceSettings = VoiceSettings()
    integrations: IntegrationsSettings = IntegrationsSettings()
    skills: SkillsSettings = SkillsSettings()
    logging: LoggingSettings = LoggingSettings()

    # Carrega YAML se existir
    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppSettings":
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            return cls(**yaml_data)
        return cls()


# Instância global
settings = AppSettings.from_yaml("config/settings.yaml")
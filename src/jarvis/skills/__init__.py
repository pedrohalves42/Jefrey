"""Sistema de Skills - Registro e descoberta dinâmica."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
import logging

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from src.jarvis.core.config import settings
from src.jarvis.core.events import event_bus, SystemEvents

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Metadados de uma skill."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Jarvis"
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = False
    config_schema: dict | None = None


class SkillBase(ABC):
    """Classe base para todas as skills."""
    
    metadata: SkillMetadata
    
    def __init__(self):
        self._tools: list[BaseTool] = []
    
    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """Retorna lista de ferramentas desta skill."""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Inicializa a skill (conexões, auth, etc). Retorna True se OK."""
        pass
    
    async def shutdown(self) -> None:
        """Cleanup ao desligar."""
        pass
    
    def is_available(self) -> bool:
        """Verifica se skill está habilitada na config."""
        return getattr(settings.skills, self.metadata.name, False)


class SkillRegistry:
    """Registro central de skills."""
    
    def __init__(self):
        self._skills: dict[str, SkillBase] = {}
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, skill: SkillBase) -> bool:
        """Registra uma skill."""
        if not skill.is_available():
            logger.info(f"Skill '{skill.metadata.name}' desabilitada na config")
            return False
        
        if not hasattr(skill, "metadata"):
            logger.error(f"Skill sem metadata: {skill.__class__.__name__}")
            return False
        
        try:
            # Inicializa
            import asyncio
            if asyncio.iscoroutinefunction(skill.initialize):
                success = asyncio.run(skill.initialize())
            else:
                success = skill.initialize()
            
            if not success:
                logger.warning(f"Falha ao inicializar skill: {skill.metadata.name}")
                return False
            
            # Registra ferramentas
            tools = skill.get_tools()
            for tool in tools:
                self._tools[tool.name] = tool
            
            self._skills[skill.metadata.name] = skill
            logger.info(f"Skill registrada: {skill.metadata.name} ({len(tools)} ferramentas)")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao registrar skill {skill.metadata.name}: {e}")
            return False
    
    def unregister(self, name: str) -> bool:
        """Remove uma skill."""
        if name in self._skills:
            skill = self._skills[name]
            import asyncio
            asyncio.run(skill.shutdown())
            
            for tool in skill.get_tools():
                self._tools.pop(tool.name, None)
            
            del self._skills[name]
            return True
        return False
    
    def get_skill(self, name: str) -> SkillBase | None:
        return self._skills.get(name)
    
    def get_all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)
    
    def list_skills(self) -> list[SkillMetadata]:
        return [s.metadata for s in self._skills.values()]
    
    def is_loaded(self, name: str) -> bool:
        return name in self._skills


# Instância global
skill_registry = SkillRegistry()


def skill(name: str, description: str, **metadata_kwargs):
    """Decorator para registrar skill automaticamente."""
    def decorator(cls):
        meta = SkillMetadata(name=name, description=description, **metadata_kwargs)
        cls.metadata = meta
        skill_registry.register(cls())
        return cls
    return decorator


def tool(name: str | None = None, description: str | None = None):
    """Decorator para criar ferramenta a partir de função async."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> BaseTool:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        # Cria schema a partir de type hints
        import inspect
        sig = inspect.signature(func)
        params = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
            default = param.default if param.default != inspect.Parameter.empty else ...
            params[param_name] = (annotation, Field(default=default, description=f"Parâmetro {param_name}"))
        
        # Cria modelo Pydantic dinamicamente
        schema = type(f"{tool_name}Schema", (BaseModel,), {
            "__annotations__": {k: v[0] for k, v in params.items()},
            **{k: v[1] for k, v in params.items()},
        })
        
        async def wrapper(**kwargs):
            return await func(**kwargs)
        
        return StructuredTool.from_function(
            coroutine=wrapper,
            name=tool_name,
            description=tool_desc,
            args_schema=schema,
        )
    return decorator
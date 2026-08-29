"""Sistema de Skills - Registro e Descoberta Dinâmica."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, get_type_hints
import inspect
import logging

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from src.jefrey.core.config import get_settings
# from src.jefrey.core.events import event_bus, SystemEvents  # Lazy import to avoid circular

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SkillMetadata:
    """Metadados de uma skill."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Jefrey Team"
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = False
    config_schema: dict | None = None
    enabled_by_default: bool = True


class SkillBase(ABC):
    """Classe base para todas as skills."""
    
    metadata: SkillMetadata
    
    def __init__(self):
        self._tools: list[BaseTool] = []
        self._initialized = False
    
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
        return getattr(get_settings().skills, self.metadata.name, False)
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized


class SkillRegistry:
    """Registro central de skills - Thread-safe."""
    
    __slots__ = ("_skills", "_tools", "_lock")
    
    def __init__(self):
        self._skills: dict[str, SkillBase] = {}
        self._tools: dict[str, BaseTool] = {}
        self._lock = __import__("threading").RLock()
    
    def register(self, skill: SkillBase) -> bool:
        """Registra uma skill."""
        with self._lock:
            if not skill.is_available():
                logger.info(f"Skill '{skill.metadata.name}' desabilitada na config")
                return False
            
            if not hasattr(skill, "metadata"):
                logger.error(f"Skill sem metadata: {skill.__class__.__name__}")
                return False
            
            if skill.metadata.name in self._skills:
                logger.warning(f"Skill '{skill.metadata.name}' já registrada, sobrescrevendo")
            
            try:
                success = skill.initialize()
                if inspect.isawaitable(success):
                    # Se já estamos em um loop, não podemos usar asyncio.run
                    # Para skills com init async, retornamos False e deixamos o agente inicializar depois
                    import asyncio
                    try:
                        asyncio.get_running_loop()
                        # Em loop - não podemos inicializar async aqui
                        logger.warning(f"Skill '{skill.metadata.name}' tem initialize async - pulando init automático")
                        return False
                    except RuntimeError:
                        # Sem loop - seguro usar asyncio.run
                        success = asyncio.run(success)
                
                if not success:
                    logger.warning(f"Falha ao inicializar skill: {skill.metadata.name}")
                    return False
                
                # Registra ferramentas
                tools = skill.get_tools()
                for tool in tools:
                    self._tools[tool.name] = tool
                
                self._skills[skill.metadata.name] = skill
                skill._initialized = True
                
                logger.info(f"Skill registrada: {skill.metadata.name} ({len(tools)} ferramentas)")
                
                # Evento - lazy import
                from src.jefrey.core.events import event_bus, SystemEvents
                import asyncio
                try:
                    asyncio.get_running_loop()
                    # Em loop - criar task
                    asyncio.create_task(event_bus.emit_sync(SystemEvents.SKILL_REGISTERED, {
                        "skill": skill.metadata.name,
                        "tools": [t.name for t in tools],
                    }))
                except RuntimeError:
                    # Sem loop - usar asyncio.run
                    asyncio.run(event_bus.emit_sync(SystemEvents.SKILL_REGISTERED, {
                        "skill": skill.metadata.name,
                        "tools": [t.name for t in tools],
                    }))
                
                return True
                
            except Exception as e:
                logger.error(f"Erro ao registrar skill {skill.metadata.name}: {e}", exc_info=True)
                return False
    
    def unregister(self, name: str) -> bool:
        """Remove uma skill."""
        with self._lock:
            if name not in self._skills:
                return False
            
            skill = self._skills[name]
            
            import asyncio
            asyncio.run(skill.shutdown())
            
            for tool in skill.get_tools():
                self._tools.pop(tool.name, None)
            
            del self._skills[name]
            
            # Emitir evento de desregistro - lazy import
            from src.jefrey.core.events import event_bus, SystemEvents
            import asyncio
            try:
                asyncio.get_running_loop()
                asyncio.create_task(event_bus.emit_sync(SystemEvents.SKILL_UNREGISTERED, {
                    "skill": name,
                }))
            except RuntimeError:
                asyncio.run(event_bus.emit_sync(SystemEvents.SKILL_UNREGISTERED, {
                    "skill": name,
                }))
            
            return True
    
    def get_skill(self, name: str) -> SkillBase | None:
        with self._lock:
            return self._skills.get(name)
    
    def get_all_tools(self) -> list[BaseTool]:
        with self._lock:
            return list(self._tools.values())
    
    def get_tool(self, name: str) -> BaseTool | None:
        with self._lock:
            return self._tools.get(name)
    
    def list_skills(self) -> list[SkillMetadata]:
        with self._lock:
            return [s.metadata for s in self._skills.values()]
    
    def is_loaded(self, name: str) -> bool:
        with self._lock:
            return name in self._skills
    
    def get_enabled_skills(self) -> list[str]:
        with self._lock:
            return [name for name, skill in self._skills.items() if skill.is_available()]


# Instância global
skill_registry = SkillRegistry()

def load_skills():
    """Carrega todas as skills (chamar após imports completos)."""
    import importlib
    import pkgutil
    
    package = __name__
    for _, module_name, _ in pkgutil.iter_modules(__path__, package + "."):
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Falha ao carregar skill {module_name}: {e}")


def skill(name: str, description: str, **metadata_kwargs):
    """Decorator para registrar skill automaticamente."""
    def decorator(cls):
        meta = SkillMetadata(name=name, description=description, **metadata_kwargs)
        cls.metadata = meta
        # Instancia e registra
        instance = cls()
        skill_registry.register(instance)
        return cls
    return decorator


def tool(name: str | None = None, description: str | None = None):
    """Decorator para criar ferramenta a partir de função async."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Any:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        # Extrai type hints
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        
        fields = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            annotation = hints.get(param_name, str)
            default = param.default if param.default != inspect.Parameter.empty else ...
            fields[param_name] = (annotation, Field(default=default, description=f"Parâmetro {param_name}"))
        
        # Cria modelo Pydantic dinamicamente
        args_schema = create_model(f"{tool_name}Schema", **fields)
        
        def make_tool(bound_func):
            async def wrapper(**kwargs):
                return await bound_func(**kwargs)
            
            return StructuredTool.from_function(
                coroutine=wrapper,
                name=tool_name,
                description=tool_desc,
                args_schema=args_schema,
            )

        class ToolDescriptor:
            def __init__(self, fn):
                self.fn = fn
                self.__name__ = tool_name
                self.__doc__ = tool_desc

            def __get__(self, obj, objtype=None):
                if obj is None:
                    return self
                bound = self.fn.__get__(obj, objtype)
                return make_tool(bound)

            def __call__(self, *args, **kwargs):
                return self.fn(*args, **kwargs)

        return ToolDescriptor(func)
    return decorator
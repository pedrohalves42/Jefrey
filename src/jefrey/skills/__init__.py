"""Sistema de Skills Jefrey - Registro e descoberta dinamica (CIPHER-034 + Axiom #7).
Refs: MCP Spec 2026-07-28, SWE cap8, Fluent cap19, CIPHER-034 versioning.
FAIL-CLOSED: skill sem metadata -> log error + return False; load_skills falha -> warn sem quebrar.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
import importlib
import logging
import inspect

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Metadados de uma skill."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Jefrey"
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = False
    config_schema: dict | None = None
    enabled_by_default: bool = True


class SkillBase(ABC):
    """Classe base para todas as skills."""

    metadata: SkillMetadata

    def __init__(self):
        self._tools: list[BaseTool] = []

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        pass

    @abstractmethod
    def initialize(self) -> bool:
        pass

    async def shutdown(self) -> None:
        pass

    def is_available(self) -> bool:
        try:
            s = get_settings().skills
            return bool(getattr(s, self.metadata.name, self.metadata.enabled_by_default if hasattr(self.metadata, 'enabled_by_default') else False))
        except Exception:
            return False


class SkillRegistry:
    """Registro central de skills - FAIL-CLOSED + LEAST PRIVILEGE."""

    def __init__(self):
        self._skills: dict[str, SkillBase] = {}
        self._tools: dict[str, BaseTool] = {}

    def register(self, skill: SkillBase) -> bool:
        if not hasattr(skill, "metadata"):
            logger.error(f"Skill sem metadata: {skill.__class__.__name__}")
            return False
        if not skill.is_available():
            logger.info(f"Skill '{skill.metadata.name}' desabilitada na config")
            return False
        try:
            import asyncio
            if asyncio.iscoroutinefunction(skill.initialize):
                success = asyncio.run(skill.initialize())
            else:
                success = skill.initialize()
            if not success:
                logger.warning(f"Falha ao inicializar skill: {skill.metadata.name}")
                return False
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
        if name in self._skills:
            skill = self._skills[name]
            import asyncio
            try:
                asyncio.run(skill.shutdown())
            except Exception:
                pass
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


# Instancia global
skill_registry = SkillRegistry()


def skill(name: str, description: str, **metadata_kwargs):
    """Decorator para registrar skill automaticamente."""
    def decorator(cls):
        meta = SkillMetadata(name=name, description=description, **metadata_kwargs)
        cls.metadata = meta
        try:
            skill_registry.register(cls())
        except Exception as e:
            logger.warning(f"skill decorator falhou {name}: {e}")
        return cls
    return decorator


def tool(name: str | None = None, description: str | None = None):
    """Decorator para criar ferramenta a partir de funcao async. Suporta metodos (self binding)."""
    def decorator(func: Callable[..., Awaitable[Any]]):
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        sig = inspect.signature(func)
        params: dict[str, tuple[Any, Any]] = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
            default = param.default if param.default != inspect.Parameter.empty else ...
            params[param_name] = (annotation, Field(default=default, description=f"Parametro {param_name}"))
        schema = type(f"{tool_name}Schema", (BaseModel,), {
            "__annotations__": {k: v[0] for k, v in params.items()},
            **{k: v[1] for k, v in params.items()},
        })
        # B1 fix: Pydantic 2.13 Any forward-ref (Fluent 19-21) — model_rebuild com Any no namespace
        try:
            schema.model_rebuild()
        except Exception:
            try:
                import sys as _sys
                _mod = _sys.modules.get(schema.__module__)
                if _mod is not None and not hasattr(_mod, "Any"):
                    setattr(_mod, "Any", Any)
                schema.model_rebuild()
            except Exception:
                pass

        # B1c fix: descriptor para bind correto de self (Fluent 19, SWE cap8)
        # Sem isto, @tool em metodo gera `missing 1 required positional argument: 'self'`
        class _ToolDescriptor:
            def __get__(self, instance, owner):
                if instance is None:
                    return self
                cache = f"_jefrey_tool_{tool_name}"
                cached = getattr(instance, cache, None)
                if cached is not None:
                    return cached
                async def bound_wrapper(**kwargs):
                    return await func(instance, **kwargs)
                bound_tool = StructuredTool.from_function(
                    coroutine=bound_wrapper,
                    name=tool_name,
                    description=tool_desc,
                    args_schema=schema,
                )
                setattr(instance, cache, bound_tool)
                return bound_tool
        return _ToolDescriptor()
    return decorator


def load_skills() -> int:
    """Importa modulos de skills para trigger dos decorators. Idempotente."""
    mods = [
        "src.jefrey.skills.notes",
        "src.jefrey.skills.automation",
        "src.jefrey.skills.calendar",
        "src.jefrey.skills.email",
        "src.jefrey.skills.web_search",
        "src.jefrey.skills.drive",
        "src.jefrey.skills.risk_assessment",
    ]
    loaded = 0
    for mod in mods:
        try:
            importlib.import_module(mod)
            loaded += 1
        except Exception as e:
            logger.debug(f"load_skills {mod} skip: {e}")
    return loaded


# Re-export version helpers (CIPHER-034)
try:
    from src.jefrey.skills.version import (
        get_skill_version,
        check_skill_compatibility,
        get_deprecated_skills,
        should_auto_upgrade,
        format_version_change_message,
    )
except Exception:
    get_skill_version = check_skill_compatibility = get_deprecated_skills = should_auto_upgrade = format_version_change_message = None  # type: ignore

__all__ = [
    "SkillBase",
    "SkillMetadata",
    "SkillRegistry",
    "skill_registry",
    "skill",
    "tool",
    "load_skills",
    "get_skill_version",
    "check_skill_compatibility",
    "get_deprecated_skills",
    "should_auto_upgrade",
    "format_version_change_message",
]

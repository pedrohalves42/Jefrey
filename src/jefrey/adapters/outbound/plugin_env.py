"""Liga os plugins ao programa real: onde ficam os arquivos, como ver as ferramentas carregadas e o catalogo de risco."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.jefrey.application.plugins import PluginStore
from src.jefrey.domain.tool_catalog import CATALOG, ToolPolicy


def tool_names() -> set[str]:
    from src.jefrey.skills import skill_registry

    return {t.name for t in skill_registry.get_all_tools()}


def mark_high_risk(names: set[str], plugin: str) -> None:
    """Ferramenta de plugin entra no catalogo como risco alto: nunca roda sem a pessoa aprovar aquela chamada."""
    for n in names:
        CATALOG.setdefault(n, ToolPolicy("high", f"Plugin {plugin}: {n}"))


_SHARED: Optional[PluginStore] = None


def shared_store() -> PluginStore:
    global _SHARED
    if _SHARED is None:
        base = Path(os.getenv("JEFREY_CONFIG_DIR", "config"))
        _SHARED = PluginStore(base / "plugins", base / "plugins_approved.json", tool_names, mark_high_risk)
    return _SHARED

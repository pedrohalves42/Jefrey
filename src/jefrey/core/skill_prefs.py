"""Preferencias do usuario: quais skills estao desligadas (config/skills.runtime.json)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


def _file() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "skills.runtime.json"


def load_disabled() -> set[str]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        names = data.get("disabled", []) if isinstance(data, dict) else []
        return {n for n in names if isinstance(n, str) and _NAME.match(n)}
    except (OSError, ValueError):
        return set()


def set_enabled(name: str, enabled: bool) -> set[str]:
    """Liga/desliga uma skill. Grava de forma atomica e devolve o conjunto de desligadas."""
    if not _NAME.match(name or ""):
        raise ValueError("nome de skill invalido")
    disabled = load_disabled()
    (disabled.discard if enabled else disabled.add)(name)
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(f.parent), prefix=".skills-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"disabled": sorted(disabled)}, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, f)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return disabled


def enabled_tools(skills: list, catalog: dict) -> dict:
    """{nome: ferramenta} so das skills ligadas e das ferramentas classificadas no catalogo."""
    off = load_disabled()
    out: dict = {}
    for sk in skills:
        if sk.metadata.name in off:
            continue
        for t in sk.get_tools():
            if t.name in catalog:
                out[t.name] = t
    return out

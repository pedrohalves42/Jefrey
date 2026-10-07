"""Onde ficam arquivos que acompanham o programa (instalado ou em desenvolvimento)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def extension_dir() -> Optional[Path]:
    """Pasta da extensao do Chrome (WhatsApp). None se nao existir."""
    candidates: list[Path] = []
    env = os.getenv("JEFREY_EXTENSION_DIR")
    if env:
        candidates.append(Path(env))
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        candidates += [base / "extensao-chrome", base / "_internal" / "extensions" / "whatsapp", base / "extensions" / "whatsapp"]
    candidates.append(Path(__file__).resolve().parents[4] / "extensions" / "whatsapp")
    for c in candidates:
        if (c / "manifest.json").is_file():
            return c
    return None


def public_extension_dir() -> Optional[Path]:
    """Copia da extensao numa pasta facil de achar e que nao muda quando o Jefrey e atualizado (Documentos/Jefrey/extensao-chrome).

    O Chrome carrega a extensao direto dessa pasta, entao ela precisa continuar no mesmo lugar depois das atualizacoes.
    """
    import shutil

    src = extension_dir()
    if src is None:
        return None
    docs = Path.home() / "Documents"
    dest = (docs if docs.is_dir() else Path.home()) / "Jefrey" / "extensao-chrome"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dest / f.name)
        return dest if (dest / "manifest.json").is_file() else src
    except OSError:
        return src

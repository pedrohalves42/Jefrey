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
    candidates.append(Path(__file__).resolve().parents[3] / "extensions" / "whatsapp")
    for c in candidates:
        if (c / "manifest.json").is_file():
            return c
    return None

"""Bootstrap do banco: cria extension vector, tabelas e índices HNSW."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.jefrey.core.schema import init_db

if __name__ == "__main__":
    init_db()

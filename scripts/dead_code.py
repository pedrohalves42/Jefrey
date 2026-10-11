"""Procura modulos Python de src/ que ninguem importa (nem o codigo, nem os testes, nem os pontos de entrada).

Uso:  python scripts/dead_code.py
Saida: lista de candidatos a remover. Importacoes por texto (importlib/strings) tambem contam, para nao dar falso positivo.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "jefrey"
ENTRY = {"src.jefrey.api.main", "src.jefrey.native.launcher", "src.jefrey.native.__main__", "src.jefrey.cli.__main__", "src.jefrey.mcp.__main__", "src.jefrey.api.__main__"}


def modname(p: Path) -> str:
    rel = p.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def main() -> int:
    mods = {modname(p): p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts}
    texts = {}
    for base in (SRC, ROOT / "tests", ROOT / "scripts", ROOT / "packaging"):
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            try:
                texts[p] = p.read_text(encoding="utf-8")
            except OSError:
                pass
    imported: dict[str, set[Path]] = {m: set() for m in mods}
    for p, t in texts.items():
        found: set[str] = set()
        try:
            tree = ast.parse(t)
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    found |= {a.name for a in n.names}
                elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                    found.add(n.module)
                    found |= {f"{n.module}.{a.name}" for a in n.names}
        except SyntaxError:
            pass
        found |= set(re.findall(r"src\.jefrey(?:\.\w+)+", t))  # importlib.import_module("...") e caminhos em texto
        for m in found:
            if m in imported and p != mods[m]:
                imported[m].add(p)
    dead = []
    for m, users in sorted(imported.items()):
        if m in ENTRY or m.endswith(".__init__") or m.endswith(".__main__"):
            continue
        # um pacote conta como usado se algum submodulo for importado de fora dele
        if not users and not any(k.startswith(m + ".") and imported[k] for k in imported):
            dead.append(m)
    print(f"{len(mods)} modulos; {len(dead)} sem nenhum importador:")
    for m in dead:
        print(f"  {m}  ({len(mods[m].read_text(encoding='utf-8').splitlines())} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

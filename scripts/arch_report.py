"""Relatorio de arquitetura: quais modulos ainda misturam regra de negocio com infraestrutura (banco, rede, framework, Windows).

Uso:  python scripts/arch_report.py
Serve para escolher o que migrar para domain/application/adapters e para acompanhar o progresso (a catraca esta em tests/test_architecture.py).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "jefrey"
INFRA = {"sqlalchemy", "httpx", "fastapi", "starlette", "chromadb", "redis", "googleapiclient", "google", "uvicorn", "pystray", "webview", "requests",
         "langchain_core", "langchain", "pydantic_settings", "ctypes", "subprocess", "winreg", "sqlite3", "psycopg", "asyncpg"}
LAYERS = ("domain", "ports", "application", "adapters", "core", "api", "skills", "native", "channels", "brain2", "eventbus", "mcp", "oauth2", "cli")


def layer_of(p: Path) -> str:
    rel = p.relative_to(ROOT).parts
    return rel[0] if rel[0] in LAYERS else "(raiz)"


def imports(p: Path) -> set[str]:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
    return out


def main() -> int:
    rows = []
    for p in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in p.parts or p.name == "__init__.py":
            continue
        imps = imports(p)
        infra = sorted({i.split(".")[0] for i in imps} & INFRA)
        lines = len(p.read_text(encoding="utf-8").splitlines())
        rows.append((layer_of(p), str(p.relative_to(ROOT)), lines, infra))
    by_layer: dict[str, list] = {}
    for r in rows:
        by_layer.setdefault(r[0], []).append(r)
    print(f"{'camada':<12}{'arquivos':>9}{'linhas':>8}{'com infra':>11}")
    for layer in LAYERS + ("(raiz)",):
        rs = by_layer.get(layer, [])
        if rs:
            print(f"{layer:<12}{len(rs):>9}{sum(r[2] for r in rs):>8}{sum(1 for r in rs if r[3]):>11}")
    print("\nCandidatos a dominio puro (em core/, sem infraestrutura, com regra de negocio):")
    for layer, name, lines, infra in rows:
        if layer == "core" and not infra and lines >= 40:
            print(f"  {name:<40}{lines:>5} linhas")
    print("\nMais misturados (core/ com 3+ tipos de infraestrutura):")
    for layer, name, lines, infra in sorted(rows, key=lambda r: -len(r[3])):
        if layer == "core" and len(infra) >= 3:
            print(f"  {name:<40}{lines:>5} linhas  {', '.join(infra)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

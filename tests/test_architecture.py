"""Arquitetura hexagonal: a regra da dependencia vale para tudo que ja foi migrado e NAO pode piorar no que ainda e antigo.

dominio  -> so biblioteca padrao e o proprio dominio
portas   -> dominio
aplicacao-> dominio, portas, aplicacao (nunca FastAPI, banco, rede, Windows nem adaptadores)
adaptadores de saida -> nao conhecem a camada de entrada (rotas)
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src" / "jefrey"
PKG = "src.jefrey"
STDLIB = set(sys.stdlib_module_names) | {"__future__"}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
    return out


def files(layer: str) -> list[Path]:
    return sorted(p for p in (ROOT / layer).rglob("*.py") if "__pycache__" not in p.parts)


def top(mod: str) -> str:
    return mod.split(".")[0]


def allowed(mod: str, inner: tuple[str, ...]) -> bool:
    if top(mod) in STDLIB:
        return True
    return any(mod == f"{PKG}.{i}" or mod.startswith(f"{PKG}.{i}.") for i in inner)


@pytest.mark.parametrize("layer,inner", [
    ("domain", ("domain",)),
    ("ports", ("domain", "ports")),
    ("application", ("domain", "ports", "application")),
])
def test_camadas_internas_so_dependem_para_dentro(layer, inner):
    ruins = []
    for p in files(layer):
        for m in imports(p):
            if not allowed(m, inner):
                ruins.append(f"{p.relative_to(ROOT)} importa {m}")
    assert not ruins, "\n".join(ruins)


def test_adaptadores_de_saida_nao_conhecem_a_entrada():
    ruins = []
    for p in files("adapters/outbound"):
        for m in imports(p):
            if m.startswith(f"{PKG}.api") or m.startswith(f"{PKG}.adapters.inbound") or top(m) in ("fastapi", "starlette"):
                ruins.append(f"{p.relative_to(ROOT)} importa {m}")
    assert not ruins, "\n".join(ruins)


def test_so_a_raiz_de_composicao_junta_casos_de_uso_e_adaptadores():
    ruins = []
    for p in files("application"):
        for m in imports(p):
            if m.startswith(f"{PKG}.adapters"):
                ruins.append(f"{p.relative_to(ROOT)} importa {m}")
    assert not ruins, "\n".join(ruins)
    assert (ROOT / "bootstrap.py").is_file()


# ---- catraca para o codigo antigo (core/): os desvios de hoje nao aumentam; ao migrar, o numero desce ----
LEGACY_CORE_IMPORTS_API = 0


def test_core_nao_depende_da_camada_de_entrada():
    n = 0
    for p in files("core"):
        n += sum(1 for m in imports(p) if m.startswith(f"{PKG}.api"))
    assert n <= LEGACY_CORE_IMPORTS_API, f"core/ passou a importar api/ ({n} vezes): isso inverte a dependencia"


# ---- core/ virou so atalhos: nenhuma infraestrutura propria ----
INFRA_LIBS = {"sqlalchemy", "httpx", "redis", "psycopg", "asyncpg", "googleapiclient", "google", "chromadb", "requests", "fastapi", "starlette",
              "prometheus_client", "opentelemetry", "langgraph", "cryptography", "pydantic", "pydantic_settings", "pythonjsonlogger", "orjson"}


def _infra_usada(layer: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for p in files(layer):
        hit = {top(m) for m in imports(p)} & INFRA_LIBS
        if hit:
            out[str(p.relative_to(ROOT))] = hit
    return out


def test_core_nao_tem_infraestrutura_propria():
    assert _infra_usada("core") == {}, "core/ so pode ter atalhos: mova bancos, rede e bibliotecas para adapters/outbound"


# as rotas e as ferramentas (adaptadores de ENTRADA) nao importam bibliotecas de infraestrutura: so chamam adapters/outbound e casos de uso
LEGACY_API_INFRA_FILES = 0  # rotas: nenhuma biblioteca de rede, banco ou Redis direta (usam adapters/outbound)
LEGACY_SKILLS_INFRA_FILES = 0  # ferramentas: nenhuma biblioteca de rede, banco ou Google direta


def test_rotas_e_ferramentas_nao_pioram():
    skills = sum(len(v - {"pydantic"}) for v in _infra_usada("skills").values())
    api_only_infra = sum(len(v - {"fastapi", "starlette", "pydantic", "prometheus_client", "cryptography"}) for v in _infra_usada("api").values())
    assert api_only_infra <= LEGACY_API_INFRA_FILES, f"api/ passou a usar mais infraestrutura direta ({api_only_infra})"
    assert skills <= LEGACY_SKILLS_INFRA_FILES, f"skills/ passou a usar mais infraestrutura direta ({skills})"

"""Modulos removidos em 2026-10 (P-07) por nao terem nenhum importador: nao devem voltar sem uso."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "jefrey"
REMOVIDOS = ["plugins", "vision", "core/compat.py", "core/schema.py", "eventbus/signing_append.py", "api/hitl_notify.py"]


def test_modulos_sem_uso_nao_voltaram():
    assert [r for r in REMOVIDOS if (ROOT / r).exists()] == []


def test_app_importa_sem_os_modulos_removidos():
    import importlib
    for m in ("src.jefrey.api.main", "src.jefrey.native.launcher", "src.jefrey.skills", "src.jefrey.core.agent_loop"):
        importlib.import_module(m)


def test_toda_pasta_de_codigo_tem_algum_importador_ou_e_ponto_de_entrada():
    """Pacotes de primeiro nivel que sobraram: cada um tem uso real (entrada, rota, skill ou teste)."""
    esperados = {"adapters", "api", "application", "brain2", "channels", "cli", "core", "domain", "eventbus", "interfaces", "legal", "mcp", "native", "oauth2", "ports", "skills", "static"}
    atuais = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("__")}
    assert atuais == esperados

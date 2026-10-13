"""Portao de lancamento: so passa quando o que depende do dono do produto esta pronto.  Rodar:  pytest -m gate tests/gates -q"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.gate


def test_textos_legais_sem_campos_em_branco():
    achados = []
    for p in (ROOT / "src" / "jefrey" / "legal").rglob("*"):
        if p.is_file():
            achados += [f"{p.name}: {m}" for m in re.findall(r"\[[A-Z][A-Z0-9 \-@\.]{2,}\]", p.read_text(encoding="utf-8", errors="ignore"))]
    assert achados == [], "preencha razao social, CNPJ e e-mail de contato nos textos legais"


def test_chave_publica_e_endereco_de_atualizacao_embutidos():
    d = ROOT / "packaging" / "defaults"
    assert (d / "update_public_key.txt").read_text(encoding="utf-8").strip(), "falta a chave publica das atualizacoes"
    url = (d / "update_url.txt").read_text(encoding="utf-8").strip() if (d / "update_url.txt").is_file() else ""
    assert url.startswith("https://"), "falta packaging/defaults/update_url.txt com o endereco https do manifest.json"


def test_google_embutido_no_instalador():
    assert (ROOT / "packaging" / "defaults" / "google_oauth.json").is_file(), "rode scripts/seed_google_defaults.py"


def test_versao_final():
    from src.jefrey import __version__
    assert not __version__.startswith("0."), f"versao {__version__} ainda e de teste"

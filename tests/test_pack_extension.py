import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pack_extension", ROOT / "scripts" / "pack_extension.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)


def test_zip_tem_manifest_na_raiz_e_so_arquivos_da_extensao(tmp_path):
    out = P.pack(ROOT / "extensions" / "whatsapp", tmp_path / "ext.zip")
    nomes = zipfile.ZipFile(out).namelist()
    assert "manifest.json" in nomes and "background.js" in nomes and "content.js" in nomes
    assert not [n for n in nomes if n.endswith((".md", ".test.js", ".map")) or "node_modules" in n or n.startswith(".")]


def test_permissoes_minimas_so_whatsapp_e_este_computador():
    m = json.loads((ROOT / "extensions" / "whatsapp" / "manifest.json").read_text(encoding="utf-8"))
    assert set(m["permissions"]) <= {"storage"}
    assert set(m["host_permissions"]) <= {"http://127.0.0.1/*", "http://localhost/*"}
    assert all(c["matches"] == ["https://web.whatsapp.com/*"] for c in m["content_scripts"])


def test_recusa_pasta_sem_manifest(tmp_path):
    (tmp_path / "x").mkdir()
    with pytest.raises(SystemExit):
        P.pack(tmp_path / "x", tmp_path / "o.zip")


def test_recusa_permissao_perigosa(tmp_path):
    d = tmp_path / "ext"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"manifest_version": 3, "name": "x", "version": "1.0.0", "permissions": ["storage", "tabs", "cookies"],
                                                 "host_permissions": ["<all_urls>"]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        P.pack(d, tmp_path / "o.zip")

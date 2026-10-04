"""Backup/restauracao: ida e volta, segredos fora, zip malicioso recusado, nada e apagado."""
import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from src.jefrey.core.backup import BackupError, create_backup, read_manifest, restore_backup

NOW = datetime(2026, 10, 4, 12, 30, 0)


@pytest.fixture()
def tree(tmp_path):
    cfg, data = tmp_path / "config", tmp_path / "data"
    (cfg / "credentials").mkdir(parents=True)
    (cfg / "tokens").mkdir()
    (cfg / "settings.yaml").write_text("a: 1", encoding="utf-8")
    (cfg / "llm.runtime.json").write_text('{"model":"x"}', encoding="utf-8")
    (cfg / "credentials" / "llm_api_key").write_text("sk-SEGREDO", encoding="utf-8")
    (cfg / "credentials" / "gmail.json").write_text("{segredo}", encoding="utf-8")
    (cfg / "tokens" / "t.json").write_text("{token}", encoding="utf-8")
    (data / "chroma_db").mkdir(parents=True)
    (data / "chroma_db" / "index.bin").write_bytes(b"\x00\x01\x02" * 100)
    (data / "files" / "ana").mkdir(parents=True)
    (data / "files" / "ana" / "nota.txt").write_text("meu texto", encoding="utf-8")
    (data / "__pycache__").mkdir()
    (data / "__pycache__" / "x.pyc").write_bytes(b"lixo")
    (data / "chroma_db" / "x.lock").write_text("", encoding="utf-8")
    return tmp_path, cfg, data


def names(p: Path):
    with zipfile.ZipFile(p) as z:
        return set(z.namelist())


def test_backup_sem_segredos_por_padrao(tree):
    root, cfg, data = tree
    out = create_backup(root / "bk", config_dir=cfg, data_dir=data, now=NOW)
    assert out.name == "jefrey-backup-20261004-123000.zip"
    n = names(out)
    assert {"config/settings.yaml", "config/llm.runtime.json", "data/chroma_db/index.bin", "data/files/ana/nota.txt", "manifest.json"} <= n
    assert not any("credentials" in x or "tokens" in x or "llm_api_key" in x for x in n)
    assert not any(x.endswith((".pyc", ".lock")) or "__pycache__" in x for x in n)
    assert read_manifest(out)["includes_secrets"] is False


def test_backup_com_segredos_so_quando_pedido(tree):
    root, cfg, data = tree
    out = create_backup(root / "bk", config_dir=cfg, data_dir=data, include_secrets=True, now=NOW)
    n = names(out)
    assert "config/credentials/llm_api_key" in n and "config/tokens/t.json" in n
    assert read_manifest(out)["includes_secrets"] is True


def test_backup_inclui_dump_do_banco(tree):
    root, cfg, data = tree
    out = create_backup(root / "bk", config_dir=cfg, data_dir=data, db_dump=lambda: b"SELECT 1;", now=NOW)
    assert "db/jefrey.sql" in names(out) and read_manifest(out)["counts"]["db"] == 1


def test_pastas_inexistentes_nao_quebram(tmp_path):
    out = create_backup(tmp_path / "bk", config_dir=tmp_path / "nada", data_dir=tmp_path / "tambem_nada", now=NOW)
    assert names(out) == {"manifest.json"}


def test_ida_e_volta(tree):
    root, cfg, data = tree
    out = create_backup(root / "bk", config_dir=cfg, data_dir=data, db_dump=lambda: b"DUMP", now=NOW)
    new_cfg, new_data = root / "novo" / "config", root / "novo" / "data"
    got = []
    r = restore_backup(out, config_dir=new_cfg, data_dir=new_data, db_restore=got.append, now=NOW)
    assert (new_cfg / "settings.yaml").read_text(encoding="utf-8") == "a: 1"
    assert (new_data / "chroma_db" / "index.bin").read_bytes() == b"\x00\x01\x02" * 100
    assert (new_data / "files" / "ana" / "nota.txt").read_text(encoding="utf-8") == "meu texto"
    assert got == [b"DUMP"] and r["db"] is True and r["moved_to"] == []
    assert not (new_cfg / "credentials").exists()


def test_restaurar_nunca_apaga_o_que_existe(tree):
    root, cfg, data = tree
    out = create_backup(root / "bk", config_dir=cfg, data_dir=data, now=NOW)
    (cfg / "settings.yaml").write_text("a: 999 (versao nova que nao pode se perder)", encoding="utf-8")
    (data / "so_existe_agora.txt").write_text("importante", encoding="utf-8")
    r = restore_backup(out, config_dir=cfg, data_dir=data, now=NOW)
    assert (cfg / "settings.yaml").read_text(encoding="utf-8") == "a: 1"  # voltou ao do backup
    moved = [Path(p) for p in r["moved_to"]]
    assert len(moved) == 2 and all(p.exists() for p in moved)
    assert any((p / "settings.yaml").read_text(encoding="utf-8").startswith("a: 999") for p in moved)
    assert any((p / "so_existe_agora.txt").exists() for p in moved)


# ---------------- zip malicioso ----------------
def evil_zip(tmp_path, *entries):
    p = tmp_path / "ruim.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("manifest.json", json.dumps({"version": 1}))
        for name, data in entries:
            z.writestr(name, data)
    return p


@pytest.mark.parametrize("nome", [
    "data/../../fora.txt", "config/../../../etc/passwd", "/etc/passwd", "data//../../x", "C:/Windows/x.txt",
    "data\\..\\..\\x.txt", "config/a/../../../x",
])
def test_zip_slip_e_caminhos_perigosos_sao_recusados(tmp_path, nome):
    z = evil_zip(tmp_path, (nome, "x"))
    with pytest.raises(BackupError):
        restore_backup(z, config_dir=tmp_path / "c", data_dir=tmp_path / "d")
    assert not (tmp_path / "fora.txt").exists()
    assert not (tmp_path / "c").exists() and not (tmp_path / "d").exists()  # nada foi tocado


def test_item_fora_das_pastas_permitidas_e_recusado(tmp_path):
    z = evil_zip(tmp_path, ("src/virus.py", "x"))
    with pytest.raises(BackupError):
        restore_backup(z, config_dir=tmp_path / "c", data_dir=tmp_path / "d")


def test_db_so_aceita_o_arquivo_esperado(tmp_path):
    z = evil_zip(tmp_path, ("db/outro.sql", "DROP DATABASE x"))
    with pytest.raises(BackupError):
        restore_backup(z, config_dir=tmp_path / "c", data_dir=tmp_path / "d", db_restore=lambda b: None)


def test_recusa_valida_tudo_antes_de_mexer_em_qualquer_coisa(tree):
    root, cfg, data = tree
    z = evil_zip(root, ("config/ok.txt", "bom"), ("data/../../fora.txt", "ruim"))
    antes = (cfg / "settings.yaml").read_text(encoding="utf-8")
    with pytest.raises(BackupError):
        restore_backup(z, config_dir=cfg, data_dir=data)
    assert (cfg / "settings.yaml").read_text(encoding="utf-8") == antes  # intacto
    assert not list(root.glob("*.antes-da-restauracao-*"))


def test_arquivo_corrompido_ou_de_outra_versao(tmp_path):
    lixo = tmp_path / "lixo.zip"
    lixo.write_bytes(b"isto nao e um zip")
    with pytest.raises(BackupError):
        read_manifest(lixo)
    with pytest.raises(BackupError):
        read_manifest(tmp_path / "nao_existe.zip")
    p = tmp_path / "v2.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("manifest.json", json.dumps({"version": 99}))
    with pytest.raises(BackupError):
        read_manifest(p)
    sem = tmp_path / "sem.zip"
    with zipfile.ZipFile(sem, "w") as z:
        z.writestr("data/x", "1")
    with pytest.raises(BackupError):
        read_manifest(sem)

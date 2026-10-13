"""Backup e restauracao do Jefrey (configuracao, memorias, arquivos e banco).

Garantias:
  - segredos (credenciais Google, tokens, chave da nuvem) ficam FORA do backup, salvo --incluir-segredos;
  - a restauracao NUNCA apaga nada: o que ja existe e movido para uma pasta ".antes-da-restauracao-...";
  - o .zip e tratado como nao confiavel: caminhos absolutos ou com ".." sao recusados (zip-slip).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

BACKUP_VERSION = 1
TOP_DIRS = ("config", "data", "db")
SECRET_NAMES = {"credentials", "tokens", "llm_api_key"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}
SKIP_SUFFIXES = (".pyc", ".tmp", ".lock", ".sock")


class BackupError(Exception):
    pass


def _is_secret(rel: Path) -> bool:
    return any(part in SECRET_NAMES for part in rel.parts)


def _iter_files(root: Path, skip_secrets: bool):
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix in SKIP_SUFFIXES:
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if skip_secrets and _is_secret(rel):
            continue
        yield p, rel


def docker_pg_dump(container: str = "jefrey-postgres") -> bytes:
    cmd = ["docker", "exec", container, "sh", "-c",
           'pg_dump -U "${POSTGRES_USER:-jefrey}" -d "${POSTGRES_DB:-jefrey}" --clean --if-exists']
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode != 0 or not r.stdout:
        raise BackupError("nao consegui exportar o banco (o container " + container + " esta rodando?)")
    return r.stdout


def docker_pg_restore(sql: bytes, container: str = "jefrey-postgres") -> None:
    cmd = ["docker", "exec", "-i", container, "sh", "-c",
           'psql -v ON_ERROR_STOP=1 -q -U "${POSTGRES_USER:-jefrey}" -d "${POSTGRES_DB:-jefrey}"']
    r = subprocess.run(cmd, input=sql, capture_output=True, timeout=600)
    if r.returncode != 0:
        raise BackupError("nao consegui restaurar o banco: " + r.stderr.decode("utf-8", "replace")[:200])


def create_backup(
    dest_dir: Path,
    *,
    config_dir: Path,
    data_dir: Path,
    include_secrets: bool = False,
    db_dump: Optional[Callable[[], bytes]] = None,
    now: Optional[datetime] = None,
) -> Path:
    """Gera <dest_dir>/jefrey-backup-AAAAMMDD-HHMMSS.zip e devolve o caminho."""
    now = now or datetime.now()
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"jefrey-backup-{now:%Y%m%d-%H%M%S}.zip"
    counts = {"config": 0, "data": 0, "db": 0}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for top, root in (("config", config_dir), ("data", data_dir)):
            for p, rel in _iter_files(root, skip_secrets=not include_secrets):
                z.write(p, f"{top}/{rel.as_posix()}")
                counts[top] += 1
        if db_dump is not None:
            z.writestr("db/jefrey.sql", db_dump())
            counts["db"] = 1
        manifest = {"version": BACKUP_VERSION, "created": now.isoformat(timespec="seconds"),
                    "includes_secrets": include_secrets, "counts": counts}
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
    return out


def read_manifest(zip_path: Path) -> dict:
    try:
        with zipfile.ZipFile(zip_path) as z:
            m = json.loads(z.read("manifest.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        raise BackupError("arquivo de backup invalido ou corrompido") from e
    if not isinstance(m, dict) or m.get("version") != BACKUP_VERSION:
        raise BackupError("versao de backup nao suportada")
    return m


def _safe_target(base: Path, name: str) -> Optional[Path]:
    """Caminho de destino dentro de `base`, ou None se o nome for perigoso."""
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or "\\" in name or ":" in pure.parts[0]:
        return None
    target = (base / Path(*pure.parts)).resolve()
    return target if base.resolve() in target.parents else None


def restore_backup(
    zip_path: Path,
    *,
    config_dir: Path,
    data_dir: Path,
    db_restore: Optional[Callable[[bytes], None]] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Restaura. O que existia e movido para '<pasta>.antes-da-restauracao-<hora>' (nada e apagado)."""
    manifest = read_manifest(zip_path)
    now = now or datetime.now()
    stamp = f"{now:%Y%m%d-%H%M%S}"
    roots = {"config": config_dir, "data": data_dir}
    restored = {"config": 0, "data": 0, "db": False, "moved_to": []}

    with zipfile.ZipFile(zip_path) as z:
        members = [i for i in z.infolist() if not i.is_dir() and i.filename != "manifest.json"]
        for info in members:  # valida TUDO antes de mexer em qualquer coisa
            top = PurePosixPath(info.filename).parts[0] if PurePosixPath(info.filename).parts else ""
            if top not in TOP_DIRS:
                raise BackupError(f"o backup contem um item inesperado: {info.filename[:60]}")
            if top in roots and _safe_target(roots[top].parent / "_check", info.filename[len(top) + 1:]) is None:
                raise BackupError("o backup contem um caminho perigoso e foi recusado")
            if top == "db" and info.filename != "db/jefrey.sql":
                raise BackupError("o backup contem um item inesperado em db/")

        # guarda o que existe (sem apagar) e recria as pastas
        selected = {PurePosixPath(i.filename).parts[0] for i in members}
        for top in ("config", "data"):
            if top in selected and roots[top].exists() and any(roots[top].iterdir()):
                keep = roots[top].with_name(roots[top].name + f".antes-da-restauracao-{stamp}")
                shutil.move(str(roots[top]), str(keep))
                restored["moved_to"].append(str(keep))
            if top in selected:
                roots[top].mkdir(parents=True, exist_ok=True)

        for info in members:
            parts = PurePosixPath(info.filename).parts
            top = parts[0]
            if top == "db":
                if db_restore is not None:
                    db_restore(z.read(info))
                    restored["db"] = True
                continue
            target = _safe_target(roots[top], "/".join(parts[1:]))
            assert target is not None  # ja validado acima
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            restored[top] += 1
    restored["manifest"] = manifest
    return restored

"""Atualizacao automatica ASSINADA.

Fluxo: o programa baixa um pequeno manifesto (JSON) do servidor de atualizacoes, confere a ASSINATURA (Ed25519, chave publica
embutida) e so entao oferece a nova versao. Ao instalar: baixa o instalador, confere o tamanho e o SHA-256 do manifesto
(assinado), faz um backup dos dados e roda o instalador. Nada instala sem a pessoa clicar; nada sem assinatura valida
e aceito; versao igual ou mais antiga e ignorada (sem "downgrade").

Manifesto:  {"version": "1.2.0", "url": "https://.../Jefrey-Setup.exe", "sha256": "...", "size": 123456, "notes": "..."}
Assinado:   a assinatura (base64) cobre a string canonica  "jefrey-update-v1|<version>|<url>|<sha256>|<size>".
Quem assina e o dono do produto, com a chave PRIVADA guardada fora deste computador (scripts/sign_update.py).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

logger = logging.getLogger(__name__)

# Chave PUBLICA de atualizacao (32 bytes em base64). TROCAR pela do dono do produto antes de vender:
#   python scripts/sign_update.py --gen-key   (guarda a privada em local seguro e copia a publica para ca)
# Pode ser sobrescrita pelo arquivo config/update_public_key.txt (util em testes e para trocar a chave sem recompilar).
PUBLIC_KEY_B64 = ""
MAX_MANIFEST = 20_000
MAX_INSTALLER = 900 * 1024 * 1024
CHUNK = 1024 * 256


class UpdateError(Exception):
    """Mensagem em portugues simples, pronta para a tela."""


def current_version() -> str:
    try:
        from src.jefrey import __version__

        return __version__
    except Exception:
        return "0.0.0"


def parse_version(v: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})", (v or "").strip())
    if not m:
        raise ValueError("versao invalida")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_newer(candidate: str, current: str) -> bool:
    try:
        return parse_version(candidate) > parse_version(current)
    except ValueError:
        return False


def canonical(m: dict) -> bytes:
    return f"jefrey-update-v1|{m['version']}|{m['url']}|{m['sha256']}|{m['size']}".encode("utf-8")


def public_key() -> Optional[Ed25519PublicKey]:
    raw = PUBLIC_KEY_B64
    f = Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "update_public_key.txt"
    try:
        if f.is_file():
            raw = f.read_text(encoding="utf-8").strip() or raw
    except OSError:
        pass
    if not raw:
        return None
    try:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(raw))
    except Exception:
        return None


def verify_manifest(m: Any, key: Optional[Ed25519PublicKey] = None) -> dict:
    """Confere formato e assinatura. Devolve o manifesto limpo ou levanta UpdateError."""
    key = key or public_key()
    if key is None:
        raise UpdateError("As atualizações automáticas ainda não estão habilitadas nesta cópia.")
    if not isinstance(m, dict):
        raise UpdateError("A resposta do servidor de atualizações não faz sentido.")
    try:
        clean = {"version": str(m["version"]), "url": str(m["url"]), "sha256": str(m["sha256"]).lower(), "size": int(m["size"]),
                 "notes": " ".join(str(m.get("notes", "")).split())[:600]}
        sig = base64.b64decode(str(m["signature"]), validate=True)
        parse_version(clean["version"])
    except (KeyError, ValueError, TypeError):
        raise UpdateError("A resposta do servidor de atualizações está incompleta.")
    if not re.fullmatch(r"[0-9a-f]{64}", clean["sha256"]) or not 1_000_000 <= clean["size"] <= MAX_INSTALLER:
        raise UpdateError("A resposta do servidor de atualizações não parece segura.")
    parts = urlsplit(clean["url"])
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise UpdateError("O endereço do instalador não é seguro (precisa ser https).")
    try:
        key.verify(sig, canonical(clean))
    except InvalidSignature:
        raise UpdateError("A assinatura da atualização não confere. Não vou instalar.")
    return clean


def manifest_url() -> str:
    """Endereco do manifesto: variavel de ambiente, ou config/update_url.txt (vem no instalador)."""
    env = os.getenv("JEFREY_UPDATE_URL", "").strip()
    if env:
        return env
    try:
        return (Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "update_url.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


async def check(*, transport: Optional[httpx.AsyncBaseTransport] = None, key: Optional[Ed25519PublicKey] = None,
                current: Optional[str] = None, url: Optional[str] = None) -> dict:
    """{available: bool, version, notes, ...}. Nunca instala nada."""
    cur = current or current_version()
    base = {"current": cur, "available": False}
    target = url if url is not None else manifest_url()
    if not target:
        return {**base, "enabled": False}
    if urlsplit(target).scheme != "https":
        raise UpdateError("O endereço de atualizações precisa ser https.")
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as c:
            r = await c.get(target)
            if r.status_code != 200 or len(r.content) > MAX_MANIFEST:
                raise UpdateError("Não consegui consultar as atualizações agora.")
            data = r.json()
    except UpdateError:
        raise
    except Exception as e:
        logger.info("atualizacao: consulta falhou (%s)", type(e).__name__)
        raise UpdateError("Não consegui consultar as atualizações agora. Verifique a internet.")
    m = verify_manifest(data, key)
    if not is_newer(m["version"], cur):
        return {**base, "enabled": True}
    return {**base, "enabled": True, "available": True, "version": m["version"], "notes": m["notes"], "size": m["size"]}


async def download(m: dict, dest_dir: Path, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> Path:
    """Baixa o instalador e confere tamanho e SHA-256 do manifesto ASSINADO. Apaga o arquivo se algo nao bater."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "Jefrey-Setup-update.exe"
    h, total = hashlib.sha256(), 0
    try:
        async with httpx.AsyncClient(timeout=60, transport=transport, follow_redirects=True) as c:
            async with c.stream("GET", m["url"]) as r:
                if r.status_code != 200:
                    raise UpdateError("Não consegui baixar a atualização agora.")
                if urlsplit(str(r.url)).scheme != "https":
                    raise UpdateError("O download foi desviado para um endereço inseguro.")
                with out.open("wb") as f:
                    async for chunk in r.aiter_bytes(CHUNK):
                        total += len(chunk)
                        if total > m["size"] or total > MAX_INSTALLER:
                            raise UpdateError("O arquivo da atualização é maior do que o esperado.")
                        h.update(chunk)
                        f.write(chunk)
        if total != m["size"] or h.hexdigest() != m["sha256"]:
            raise UpdateError("O arquivo baixado não confere com o esperado. Não vou instalar.")
        return out
    except UpdateError:
        out.unlink(missing_ok=True)
        raise
    except Exception as e:
        out.unlink(missing_ok=True)
        logger.info("atualizacao: download falhou (%s)", type(e).__name__)
        raise UpdateError("Não consegui baixar a atualização agora. Verifique a internet.")


def backup_before_update(home: Path) -> Optional[Path]:
    """Copia os dados (sem chaves) antes de instalar. Melhor esforco: sem backup a atualizacao ainda e segura (os dados nao sao tocados)."""
    try:
        from src.jefrey.core.backup import create_backup

        return create_backup(home / "backups", config_dir=home / "config", data_dir=home / "data")
    except Exception as e:
        logger.warning("backup antes de atualizar falhou (%s)", type(e).__name__)
        return None


def run_installer(path: Path) -> None:
    """Roda o instalador em modo silencioso (ele fecha o Jefrey, instala por cima e reabre). So no Windows."""
    if sys.platform != "win32":
        raise UpdateError("A atualização automática só existe no Windows.")
    subprocess.Popen([str(path), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS", "/NOCANCEL"], close_fds=True)


async def install(*, transport: Optional[httpx.AsyncBaseTransport] = None, key: Optional[Ed25519PublicKey] = None, home: Optional[Path] = None,
                  runner=run_installer, url: Optional[str] = None, current: Optional[str] = None) -> dict:
    """Confere de novo (nao confia no que a tela viu), baixa, verifica, faz backup e instala."""
    target = url if url is not None else manifest_url()
    if not target or urlsplit(target).scheme != "https":
        raise UpdateError("As atualizações automáticas não estão habilitadas.")
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as c:
            r = await c.get(target)
            data = r.json() if r.status_code == 200 and len(r.content) <= MAX_MANIFEST else None
    except Exception:
        data = None
    if data is None:
        raise UpdateError("Não consegui consultar as atualizações agora.")
    m = verify_manifest(data, key)
    if not is_newer(m["version"], current or current_version()):
        raise UpdateError("Você já está com a versão mais nova.")
    home = home or Path(os.getenv("JEFREY_HOME") or (Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Jefrey"))
    backup = backup_before_update(home)
    path = await download(m, Path(tempfile.gettempdir()) / "jefrey-update", transport=transport)
    runner(path)
    return {"started": True, "version": m["version"], "backup": backup.name if backup else None}

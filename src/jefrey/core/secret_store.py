"""Cofre de chaves: no Windows usa DPAPI (so o mesmo usuario do Windows, neste computador, consegue abrir).

Fora do Windows grava com permissao 0600 (melhor esforco). Arquivos antigos em texto puro continuam
legiveis e sao regravados protegidos na proxima gravacao. Nunca registra o valor em log.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Optional

PREFIX = "dpapi1:"
_ID = re.compile(r"^[a-z0-9_-]{1,40}$")


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    inb = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    outb = Blob()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(inb), None, None, None, None, 0, ctypes.byref(outb))
    if not ok:
        raise OSError("DPAPI falhou")
    try:
        return ctypes.string_at(outb.pbData, outb.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(outb.pbData)


def protect(text: str) -> str:
    if os.name == "nt":
        return PREFIX + base64.urlsafe_b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii")
    return text


def unprotect(stored: str) -> str:
    stored = stored.strip()
    if stored.startswith(PREFIX):
        if os.name != "nt":
            raise OSError("segredo protegido pelo Windows nao pode ser aberto neste sistema")
        return _dpapi(base64.urlsafe_b64decode(stored[len(PREFIX):]), False).decode("utf-8")
    return stored  # formato antigo (texto puro)


def valid_id(key_id: str) -> bool:
    return bool(_ID.match(key_id or ""))


def write_secret(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(protect(value.strip()), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def read_secret(path: Path) -> Optional[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.strip():
        return None
    try:
        return unprotect(raw) or None
    except (OSError, ValueError):
        return None

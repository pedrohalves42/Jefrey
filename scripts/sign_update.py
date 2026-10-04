"""Assinar uma atualizacao do Jefrey (feito pelo DONO do produto, fora do computador dos clientes).

1) Uma vez:   python scripts/sign_update.py --gen-key
              -> grava update_private_key.txt (GUARDE em local seguro, NUNCA no repositorio) e mostra a chave publica para colar em
                 PUBLIC_KEY_B64 em src/jefrey/core/updater.py (ou em config/update_public_key.txt).
2) A cada versao:
   python scripts/sign_update.py --key update_private_key.txt --installer packaging/Output/Jefrey-Setup.exe \
          --version 1.2.0 --url https://exemplo.com/downloads/Jefrey-Setup-1.2.0.exe --notes "O que mudou" --out manifest.json
   -> publique o instalador no endereco informado e o manifest.json no endereco de atualizacoes (JEFREY_UPDATE_URL).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

RAW = serialization.Encoding.Raw


def canonical(m: dict) -> bytes:
    return f"jefrey-update-v1|{m['version']}|{m['url']}|{m['sha256']}|{m['size']}".encode("utf-8")


def gen_key(path: Path) -> str:
    if path.exists():
        raise SystemExit(f"{path} ja existe: nao vou sobrescrever uma chave.")
    priv = Ed25519PrivateKey.generate()
    path.write_text(base64.b64encode(priv.private_bytes(RAW, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode(), encoding="utf-8")
    return base64.b64encode(priv.public_key().public_bytes(RAW, serialization.PublicFormat.Raw)).decode()


def build_manifest(key_path: Path, installer: Path, version: str, url: str, notes: str) -> dict:
    priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key_path.read_text(encoding="utf-8").strip()))
    data = installer.read_bytes()
    m = {"version": version, "url": url, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "notes": notes}
    m["signature"] = base64.b64encode(priv.sign(canonical(m))).decode()
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-key", action="store_true")
    ap.add_argument("--key", type=Path, default=Path("update_private_key.txt"))
    ap.add_argument("--installer", type=Path)
    ap.add_argument("--version")
    ap.add_argument("--url")
    ap.add_argument("--notes", default="")
    ap.add_argument("--out", type=Path, default=Path("manifest.json"))
    a = ap.parse_args()
    if a.gen_key:
        pub = gen_key(a.key)
        print(f"Chave privada gravada em {a.key} (GUARDE em local seguro).\nChave PUBLICA (cole em PUBLIC_KEY_B64):\n{pub}")
        return 0
    if not (a.installer and a.version and a.url):
        ap.error("informe --installer, --version e --url")
    m = build_manifest(a.key, a.installer, a.version, a.url, a.notes)
    a.out.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifesto assinado em {a.out}: versao {m['version']}, {m['size']} bytes, sha256 {m['sha256'][:12]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())

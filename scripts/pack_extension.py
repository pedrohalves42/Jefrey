"""Empacota a extensao do WhatsApp em um .zip pronto para a Chrome Web Store.

Uso:  python scripts/pack_extension.py [pasta_da_extensao] [saida.zip]
Recusa empacotar se o manifest pedir permissoes alem de `storage` ou enderecos alem do WhatsApp Web e deste computador.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PERMISSIONS = {"storage"}
ALLOWED_HOSTS = {"http://127.0.0.1/*", "http://localhost/*"}
SKIP_SUFFIXES = (".md", ".map")


def check_manifest(m: dict) -> None:
    perms = set(m.get("permissions", [])) - ALLOWED_PERMISSIONS
    hosts = set(m.get("host_permissions", [])) - ALLOWED_HOSTS
    if perms or hosts:
        raise SystemExit(f"Permissões não permitidas no manifest: {sorted(perms | hosts)}")
    for c in m.get("content_scripts", []):
        if c.get("matches") != ["https://web.whatsapp.com/*"]:
            raise SystemExit("A extensão só pode agir em https://web.whatsapp.com/*")


def pack(src: Path, out: Path) -> Path:
    src, out = Path(src), Path(out)
    mf = src / "manifest.json"
    if not mf.is_file():
        raise SystemExit(f"{src} não tem manifest.json")
    check_manifest(json.loads(mf.read_text(encoding="utf-8")))
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.rglob("*")):
            rel = f.relative_to(src)
            if f.is_file() and not f.name.startswith(".") and not f.name.endswith(SKIP_SUFFIXES) and ".test." not in f.name and "node_modules" not in rel.parts:
                z.write(f, rel.as_posix())
    return out


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "extensions" / "whatsapp"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "release" / "jefrey-whatsapp-extensao.zip"
    print("Pacote:", pack(src, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

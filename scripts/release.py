"""Publicar uma versao do Jefrey: confere tudo, gera o manifesto ASSINADO e a pasta release/<versao>/.

Uso:
  python scripts/release.py 1.0.0 --url-base https://SEU-SITE/downloads --key C:/Users/Pedro/Jefrey-chaves/update_private_key.txt --notes "O que mudou"
  (acrescente --run para rodar testes e gerar o instalador; sem --run so mostra o plano e usa o instalador ja gerado)

Saida: release/<versao>/Jefrey-Setup-<versao>.exe e manifest.json. Suba os dois para o seu site (docs/PUBLICAR.md).
A chave PRIVADA nunca e copiada nem fica dentro do repositorio.
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MIN_INSTALLER = 1_000_000  # o programa instalado recusa manifestos com instalador menor que isso


def _sign_module():
    spec = importlib.util.spec_from_file_location("sign_update", ROOT / "scripts" / "sign_update.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check_version(version: str, current: str | None = None) -> str:
    from src.jefrey.core.updater import is_newer, parse_version

    if current is None:
        from src.jefrey import __version__ as current
    try:
        parse_version(version)
    except ValueError:
        raise SystemExit(f"Versão inválida: {version!r} (use 1.2.3).")
    if not is_newer(version, current):
        raise SystemExit(f"A versão {version} não é maior que a atual ({current}).")
    return version


def plan(version: str) -> list[str]:
    return [
        "1. python -m pytest tests -q --ignore=tests/e2e --ignore=tests/smoke  (tudo verde)",
        "1b. python -m pytest tests/gates -m gate -q  (portao: textos legais, chave e endereco de atualizacao, Google, versao)",
        "2. cd ui && npx tsc --noEmit -p . && npx vitest run && npm run build:api",
        f"3. aumentar __version__ para {version} em src/jefrey/__init__.py e config.py",
        "4. packaging\\build_exe.bat  (gera e, se houver certificado, assina o instalador)",
        "5. gerar o manifest assinado com a chave privada (fora do repositorio)",
        f"6. subir release/{version}/ para o site e conferir o endereço em packaging/defaults/update_url.txt",
    ]


def make_release(version: str, url_base: str, key: Path, installer: Path, out_root: Path, notes: str, current: str | None = None) -> Path:
    check_version(version, current)
    key, installer = Path(key).resolve(), Path(installer)
    if ROOT in key.parents:
        raise SystemExit("A chave privada não pode ficar dentro do repositório. Guarde fora (ex.: C:/Users/Pedro/Jefrey-chaves).")
    parts = urlsplit(url_base)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise SystemExit("O endereço de download precisa ser https.")
    if not installer.is_file() or installer.stat().st_size < MIN_INSTALLER:
        raise SystemExit(f"Instalador não encontrado ou pequeno demais: {installer}")
    out = Path(out_root) / version
    out.mkdir(parents=True, exist_ok=True)
    name = f"Jefrey-Setup-{version}.exe"
    shutil.copy2(installer, out / name)
    url = url_base.rstrip("/") + "/" + name
    sign = _sign_module()
    m = sign.build_manifest(key, out / name, version, url, notes)
    import json

    (out / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--url-base", required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--installer", type=Path, default=ROOT / "packaging" / "Output" / "Jefrey-Setup.exe")
    ap.add_argument("--notes", default="")
    ap.add_argument("--run", action="store_true", help="roda os testes e gera o instalador antes")
    a = ap.parse_args()
    check_version(a.version)
    print("\n".join(plan(a.version)))
    if a.run:
        py = sys.executable
        subprocess.run([py, "-m", "pytest", "tests", "-q", "--ignore=tests/e2e", "--ignore=tests/smoke", "-p", "no:warnings"], cwd=ROOT, check=True)
        subprocess.run(["cmd", "/c", "packaging\\build_exe.bat", py], cwd=ROOT, check=True)
    out = make_release(a.version, a.url_base, a.key, a.installer, ROOT / "release", a.notes)
    print("Pronto:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

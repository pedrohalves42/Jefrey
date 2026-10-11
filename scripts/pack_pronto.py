"""Gera a pasta "Jefrey-Pronto" (projeto limpo + instalador) de forma reproduzivel.

Uso:  python scripts/pack_pronto.py [pasta_de_destino]      (padrao: Desktop/Jefrey-Pronto)
Conteudo: so os arquivos versionados no Git (HEAD) + a chave PUBLICA das atualizacoes + o instalador gerado + LEIA-ME.txt.
Nunca entram: .env, certificados, chaves privadas, credenciais do Google (o instalador ja as leva embutidas).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = (".pfx", ".p12", ".snk", ".pem", ".key")
FORBIDDEN_NAMES = ("google_oauth.json", "update_private_key.txt")

LEIA_ME = """JEFREY - PASTA PRONTA

instalador\\Jefrey-Setup.exe   O programa para instalar no Windows (duplo clique).
projeto\\                      O projeto limpo: so os arquivos do codigo-fonte (sem chaves, sem dados, sem cache).

Para gerar um instalador novo a partir de "projeto\\" (Windows, Python 3.12, Inno Setup):
  1. Coloque em projeto\\packaging\\defaults\\ o que quiser embutir:
       google_oauth.json     (credenciais do app Google: python scripts/seed_google_defaults.py no projeto original)
       update_url.txt        (endereco https do manifest.json das atualizacoes)
       update_public_key.txt (ja vem; chave PUBLICA das atualizacoes)
  2. packaging\\build_exe.bat C:\\caminho\\do\\python3.12.exe
  3. Para assinar e publicar: projeto\\docs\\PUBLICAR.md

A chave PRIVADA das atualizacoes NAO esta aqui. Guarde uma copia fora do computador.
"""


def _git_archive(root: Path) -> bytes:
    return subprocess.run(["git", "archive", "HEAD"], cwd=root, check=True, capture_output=True).stdout


def pack(root: Path, dest: Path, installer: Path | None = None) -> Path:
    root, dest = Path(root), Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    proj = dest / "projeto"
    proj.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(_git_archive(root))) as tar:
        for m in tar.getmembers():
            name = Path(m.name).name.lower()
            if name.endswith(FORBIDDEN_SUFFIXES) or name in FORBIDDEN_NAMES or (name.startswith(".env") and name != ".env.example"):
                continue  # mesmo que alguem tenha versionado por engano
            tar.extract(m, proj, filter="data")
    pub = root / "packaging" / "defaults" / "update_public_key.txt"
    if pub.is_file():
        (proj / "packaging" / "defaults").mkdir(parents=True, exist_ok=True)
        shutil.copy2(pub, proj / "packaging" / "defaults" / "update_public_key.txt")
    inst = installer or root / "packaging" / "Output" / "Jefrey-Setup.exe"
    if Path(inst).is_file():
        (dest / "instalador").mkdir()
        shutil.copy2(inst, dest / "instalador" / "Jefrey-Setup.exe")
    (dest / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")
    return dest


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "Jefrey-Pronto"
    print("Pasta pronta:", pack(ROOT, dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())

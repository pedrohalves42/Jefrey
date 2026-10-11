"""Deixa o "Entrar com o Google" pronto para 1 clique no instalador.

Le JEFREY_OAUTH__CLIENT_ID e JEFREY_OAUTH__CLIENT_SECRET do seu .env (ou das variaveis de ambiente) e grava
packaging/defaults/google_oauth.json (fora do Git). Nao mostra os valores. Depois e so gerar o instalador de novo.

Uso:  python scripts/seed_google_defaults.py            (grava em packaging/defaults)
      python scripts/seed_google_defaults.py --instalado   (grava tambem na pasta de dados deste computador)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def from_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"\s*(JEFREY_OAUTH__CLIENT_(?:ID|SECRET)|JEFREY_OAUTH__REDIRECT_URIS)\s*=\s*(.*?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2).strip().strip("\"'")
    return out


def main() -> int:
    vals = from_env_file(ROOT / ".env")
    cid = os.getenv("JEFREY_OAUTH__CLIENT_ID") or vals.get("JEFREY_OAUTH__CLIENT_ID", "")
    sec = os.getenv("JEFREY_OAUTH__CLIENT_SECRET") or vals.get("JEFREY_OAUTH__CLIENT_SECRET", "")
    if not (cid and sec):
        print("Nao achei JEFREY_OAUTH__CLIENT_ID / JEFREY_OAUTH__CLIENT_SECRET no .env. Veja docs/GOOGLE.md.")
        return 1
    if not cid.endswith(".apps.googleusercontent.com"):
        print("O ID do cliente nao parece valido (deve terminar com .apps.googleusercontent.com).")
        return 1
    uris = [u.strip() for u in (os.getenv("JEFREY_OAUTH__REDIRECT_URIS") or vals.get("JEFREY_OAUTH__REDIRECT_URIS", "")).split(",") if u.strip()]
    inner = {"client_id": cid, "client_secret": sec}
    if uris:  # cliente "Aplicativo da Web": so aceita os enderecos de retorno ja registrados
        inner["redirect_uris"] = uris
    data = json.dumps({"installed": inner})
    targets = [ROOT / "packaging" / "defaults" / "google_oauth.json"]
    if "--instalado" in sys.argv:
        home = Path(os.getenv("JEFREY_HOME") or (Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Jefrey"))
        targets.append(home / "config" / "google_oauth.json")
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(data, encoding="utf-8")
        print("Gravado:", t)
    print("Pronto. Gere o instalador de novo (packaging\\build_exe.bat) para o 1 clique vir embutido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

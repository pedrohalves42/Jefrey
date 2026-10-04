"""Gera docs/LICENCAS_TERCEIROS.md com a licenca de cada biblioteca de que o Jefrey depende (requirements.txt).

Uso:  C:\\Users\\Pedro\\jv312\\Scripts\\python.exe scripts/gen_licenses.py
Avisa as que tem licenca copyleft forte (GPL/AGPL) ou desconhecida: precisam de decisao do dono antes de vender.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRONG = re.compile(r"\b(AGPL|GPL)\b", re.I)
WEAK = re.compile(r"\b(LGPL|MPL|EPL)\b", re.I)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def wanted() -> list[str]:
    names = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)", line)
        if m:
            names.append(m.group(1))
    return sorted(set(names), key=str.lower)


def license_of(dist: metadata.Distribution) -> str:
    md = dist.metadata
    expr = md.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (md.get("License") or "").strip()
    if lic and len(lic) < 80 and "\n" not in lic:
        return lic
    classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return "; ".join(classifiers)
    return lic.splitlines()[0][:80] if lic else "DESCONHECIDA"


def main() -> int:
    rows, strong, weak, unknown, missing = [], [], [], [], []
    installed = {norm(d.metadata["Name"]): d for d in metadata.distributions() if d.metadata["Name"]}
    for name in wanted():
        d = installed.get(norm(name))
        if d is None:
            missing.append(name)
            continue
        lic = license_of(d)
        rows.append((d.metadata["Name"], d.version, lic, (d.metadata.get("Home-page") or d.metadata.get("Project-URL") or "").split(",")[-1].strip()))
        if lic == "DESCONHECIDA":
            unknown.append(d.metadata["Name"])
        elif STRONG.search(lic) and not WEAK.search(lic):
            strong.append(f"{d.metadata['Name']} ({lic})")
        elif WEAK.search(lic):
            weak.append(f"{d.metadata['Name']} ({lic})")
    out = ["# Licenças de terceiros", "", "Gerado por `scripts/gen_licenses.py` a partir do `requirements.txt` instalado. Reveja antes de vender.", "",
           "| Biblioteca | Versão | Licença |", "|---|---|---|"]
    out += [f"| {n} | {v} | {l} |" for n, v, l, _ in rows]
    out += ["", "## Atenção"]
    out += [f"- **Copyleft forte (decidir antes de vender):** {', '.join(strong) or 'nenhuma encontrada'}",
            f"- **Copyleft fraco (ok se só usada como biblioteca, sem alterar):** {', '.join(weak) or 'nenhuma'}",
            f"- **Licença não identificada (conferir manualmente):** {', '.join(unknown) or 'nenhuma'}",
            f"- **Listadas no requirements mas não instaladas aqui:** {', '.join(missing) or 'nenhuma'}",
            "- O PyInstaller (usado só para empacotar) tem exceção que permite distribuir o programa gerado sob a licença que você escolher.",
            "- Os modelos de voz (Whisper, via faster-whisper) são MIT; os modelos de IA locais e as vozes do Windows têm licenças próprias."]
    (ROOT / "docs" / "LICENCAS_TERCEIROS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(rows)} bibliotecas; copyleft forte: {len(strong)}; fraco: {len(weak)}; desconhecidas: {len(unknown)}; ausentes: {len(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

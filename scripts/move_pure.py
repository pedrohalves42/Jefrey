"""Move modulos de core/ para a camada certa (domain/ ou application/) deixando um atalho no lugar antigo.

O atalho TROCA o modulo em sys.modules pelo novo: `from src.jefrey.core import persona` e `monkeypatch` continuam funcionando
e quem importava o nome antigo nao precisa mudar agora. Uso: python scripts/move_pure.py domain wakeword persona ...
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "jefrey"
layer, names = sys.argv[1], sys.argv[2:]
assert layer in ("domain", "application")
for n in names:
    src = ROOT / "core" / f"{n}.py"
    dst = ROOT / layer / f"{n}.py"
    assert src.is_file() and not dst.exists(), n
    text = src.read_text(encoding="utf-8")
    assert "sys.modules[__name__]" not in text, f"{n} ja e um atalho"
    dst.write_text(text, encoding="utf-8")
    src.write_text(
        f'"""Atalho de compatibilidade: este modulo agora mora em {layer}/{n}.py."""\n'
        f"import sys\n\n"
        f"from src.jefrey.{layer} import {n} as _moved\n\n"
        f"sys.modules[__name__] = _moved\n",
        encoding="utf-8",
    )
    print("movido:", n, "->", layer)

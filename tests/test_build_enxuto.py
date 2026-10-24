"""O instalador so leva as APIs do Google que o Jefrey usa; se alguem passar a usar outra, o teste avisa para manter o documento."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEPT = {"calendar.v3.json", "drive.v3.json", "gmail.v1.json"}


def _used() -> set[str]:
    used = set()
    for p in (ROOT / "src" / "jefrey").rglob("*.py"):
        for svc, ver in re.findall(r"build\(\s*['\"]([a-z]+)['\"],\s*['\"]([a-z0-9]+)['\"]", p.read_text(encoding="utf-8", errors="ignore")):
            used.add(f"{svc}.{ver}.json")
    return used


def test_todo_servico_do_google_usado_esta_na_lista_mantida_pelo_build():
    assert _used() <= KEPT, f"o codigo usa {_used() - KEPT}: acrescente em packaging/build_exe.bat"


def test_build_mantem_so_esses_tres():
    bat = (ROOT / "packaging" / "build_exe.bat").read_text(encoding="utf-8")
    assert all(name in bat for name in KEPT)
    assert "discovery_cache" in bat

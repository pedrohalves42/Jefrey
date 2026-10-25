import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pack_pronto", ROOT / "scripts" / "pack_pronto.py")
PP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PP)


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    (r / "packaging" / "defaults").mkdir(parents=True)
    (r / "src" / "app.py").write_text("print(1)", encoding="utf-8")
    (r / ".env.example").write_text("X=", encoding="utf-8")
    (r / ".env").write_text("SEGREDO=abc", encoding="utf-8")  # versionado por engano
    (r / "cert.pfx").write_bytes(b"x")
    (r / "packaging" / "defaults" / "google_oauth.json").write_text("{}", encoding="utf-8")
    (r / "packaging" / "defaults" / "update_public_key.txt").write_text("PUB", encoding="utf-8")
    (r / "naoversionado.txt").write_text("fora", encoding="utf-8")
    run = lambda *a: subprocess.run(["git", *a], cwd=r, check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    run("add", "-f", "src", ".env.example", ".env", "cert.pfx", "packaging")
    run("commit", "-q", "-m", "x")
    return r


def _arquivos(d: Path) -> list[str]:
    return sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())


def test_so_arquivos_versionados_sem_segredos_mesmo_se_versionados_por_engano(repo, tmp_path):
    inst = tmp_path / "Jefrey-Setup.exe"
    inst.write_bytes(b"MZ")
    out = PP.pack(repo, tmp_path / "pronto", installer=inst)
    arq = _arquivos(out)
    assert "projeto/src/app.py" in arq and "projeto/.env.example" in arq
    assert "projeto/naoversionado.txt" not in arq
    assert not [a for a in arq if a.endswith((".pfx", "/.env", "google_oauth.json"))]
    assert "projeto/packaging/defaults/update_public_key.txt" in arq  # a chave PUBLICA vai
    assert "instalador/Jefrey-Setup.exe" in arq and "LEIA-ME.txt" in arq


def test_reproduzivel_duas_execucoes_mesma_lista(repo, tmp_path):
    a = _arquivos(PP.pack(repo, tmp_path / "a"))
    b = _arquivos(PP.pack(repo, tmp_path / "b"))
    assert a == b


def test_sobrescreve_pasta_antiga(repo, tmp_path):
    d = tmp_path / "pronto"
    d.mkdir()
    (d / "lixo.txt").write_text("velho", encoding="utf-8")
    PP.pack(repo, d)
    assert not (d / "lixo.txt").exists()


def test_leia_me_nao_manda_colocar_chave_privada_no_pacote():
    assert "chave PRIVADA" in PP.LEIA_ME and "NAO esta aqui" in PP.LEIA_ME

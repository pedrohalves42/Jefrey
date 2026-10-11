import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jefrey.core import updater as U

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = _load("release")


@pytest.fixture()
def chaves(tmp_path):
    priv = Ed25519PrivateKey.generate()
    raw = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    kp = tmp_path / "chaves" / "update_private_key.txt"
    kp.parent.mkdir()
    kp.write_text(base64.b64encode(raw).decode(), encoding="utf-8")
    return kp, priv.public_key()


@pytest.fixture()
def instalador(tmp_path):
    f = tmp_path / "Jefrey-Setup.exe"
    f.write_bytes(b"MZ" + b"\x00" * 1_200_000)
    return f


def test_recusa_versao_menor_ou_igual_e_invalida():
    for v in ("0.9.0", "0.8.9", "abc", "1.0"):
        with pytest.raises(SystemExit):
            R.check_version(v, current="0.9.0")
    assert R.check_version("1.0.0", current="0.9.0") == "1.0.0"


def test_manifesto_assinado_confere_com_a_chave_publica(tmp_path, chaves, instalador):
    kp, pub = chaves
    out = R.make_release("1.0.0", "https://exemplo.com/dl", kp, instalador, tmp_path / "release", notes="Primeira versão", current="0.9.0")
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    ok = U.verify_manifest(m, pub)  # mesma conferencia que o programa instalado faz
    assert ok["version"] == "1.0.0" and ok["url"] == "https://exemplo.com/dl/Jefrey-Setup-1.0.0.exe"
    assert ok["sha256"] == hashlib.sha256(instalador.read_bytes()).hexdigest() and ok["size"] == instalador.stat().st_size


def test_pasta_de_release_so_tem_instalador_e_manifesto(tmp_path, chaves, instalador):
    kp, _ = chaves
    out = R.make_release("1.0.0", "https://exemplo.com/dl", kp, instalador, tmp_path / "release", notes="", current="0.9.0")
    assert sorted(p.name for p in out.iterdir()) == ["Jefrey-Setup-1.0.0.exe", "manifest.json"]
    todo = b" ".join(p.read_bytes() for p in out.iterdir() if p.suffix == ".json")
    assert kp.read_text(encoding="utf-8").strip().encode() not in todo  # a chave privada nunca vai junto


def test_recusa_endereco_sem_https_e_instalador_pequeno(tmp_path, chaves, instalador):
    kp, _ = chaves
    with pytest.raises(SystemExit):
        R.make_release("1.0.0", "http://exemplo.com/dl", kp, instalador, tmp_path / "r", notes="", current="0.9.0")
    pequeno = tmp_path / "p.exe"
    pequeno.write_bytes(b"MZ")
    with pytest.raises(SystemExit):
        R.make_release("1.0.0", "https://exemplo.com/dl", kp, pequeno, tmp_path / "r2", notes="", current="0.9.0")


def test_recusa_chave_privada_dentro_do_repositorio(tmp_path, instalador):
    dentro = ROOT / "update_private_key_teste.txt"
    dentro.write_text("x", encoding="utf-8")
    try:
        with pytest.raises(SystemExit, match="repositório"):
            R.make_release("1.0.0", "https://exemplo.com/dl", dentro, instalador, tmp_path / "r", notes="", current="0.9.0")
    finally:
        dentro.unlink()


def test_plano_lista_os_passos_na_ordem():
    passos = R.plan("1.0.0")
    texto = " | ".join(passos)
    assert texto.index("pytest") < texto.index("build_exe") < texto.index("manifest") and "vitest" in texto

"""Do script de release ao programa instalado: o manifesto que release.py gera e aceito de ponta a ponta por updater.check/install."""
import asyncio
import base64
import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jefrey.core import updater as U

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("release", ROOT / "scripts" / "release.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def cenario(tmp_path):
    priv = Ed25519PrivateKey.generate()
    kp = tmp_path / "chaves" / "k.txt"
    kp.parent.mkdir()
    kp.write_text(base64.b64encode(priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode(), encoding="utf-8")
    inst = tmp_path / "Jefrey-Setup.exe"
    inst.write_bytes(b"MZ" + b"\x07" * 1_300_000)
    out = R.make_release("1.0.0", "https://dl.exemplo.com/jefrey", kp, inst, tmp_path / "release", notes="Primeira versão", current="0.9.0")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    exe = (out / "Jefrey-Setup-1.0.0.exe").read_bytes()

    def servidor(corpo_exe=exe):
        def handler(req: httpx.Request):
            if req.url.path.endswith("manifest.json"):
                return httpx.Response(200, json=manifest)
            if req.url.path.endswith(".exe"):
                return httpx.Response(200, content=corpo_exe)
            return httpx.Response(404)
        return httpx.MockTransport(handler)
    return priv.public_key(), servidor


def test_programa_antigo_ve_a_versao_nova_gerada_pelo_release(cenario):
    pub, servidor = cenario
    r = run(U.check(transport=servidor(), key=pub, current="0.9.0", url="https://dl.exemplo.com/manifest.json"))
    assert r["available"] is True and r["version"] == "1.0.0" and r["notes"] == "Primeira versão"


def test_programa_na_versao_nova_nao_ve_nada(cenario):
    pub, servidor = cenario
    r = run(U.check(transport=servidor(), key=pub, current="1.0.0", url="https://dl.exemplo.com/manifest.json"))
    assert r["available"] is False


def test_instala_roda_o_instalador_baixado(cenario, tmp_path):
    pub, servidor = cenario
    rodou = []
    out = run(U.install(transport=servidor(), key=pub, home=tmp_path / "home", runner=rodou.append, url="https://dl.exemplo.com/manifest.json", current="0.9.0"))
    assert out["started"] is True and out["version"] == "1.0.0" and len(rodou) == 1
    assert rodou[0].read_bytes()[:2] == b"MZ"


def test_instalador_adulterado_no_caminho_nunca_roda(cenario, tmp_path):
    pub, servidor = cenario
    rodou = []
    with pytest.raises(U.UpdateError, match="confere"):
        run(U.install(transport=servidor(b"MZ" + b"\x00" * 1_300_000), key=pub, home=tmp_path / "home", runner=rodou.append,
                      url="https://dl.exemplo.com/manifest.json", current="0.9.0"))
    assert rodou == []


def test_chave_publica_de_outra_pessoa_recusa_o_manifesto(cenario):
    _, servidor = cenario
    outra = Ed25519PrivateKey.generate().public_key()
    with pytest.raises(U.UpdateError, match="assinatura"):
        run(U.check(transport=servidor(), key=outra, current="0.9.0", url="https://dl.exemplo.com/manifest.json"))

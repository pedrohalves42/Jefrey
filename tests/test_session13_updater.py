"""Sessao 13 (parte 2): atualizacao automatica ASSINADA (assinatura, hash, sem downgrade, backup, nada instala sem confirmar)."""
import asyncio
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from src.jefrey.core import updater as U

ROOT = Path(__file__).resolve().parents[1]
URL_MANIFESTO = "https://atualizacoes.exemplo.com/manifest.json"
URL_INSTALADOR = "https://downloads.exemplo.com/Jefrey-Setup-1.2.0.exe"
INSTALADOR = (b"MZ-instalador-de-teste" + bytes(1_100_000))


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def signer():
    spec = importlib.util.spec_from_file_location("sign_update", ROOT / "scripts" / "sign_update.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sign_update"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def chaves(tmp_path, signer):
    priv = tmp_path / "priv.txt"
    pub_b64 = signer.gen_key(priv)
    key = U.Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))
    return priv, key, tmp_path


def manifesto(signer, priv, tmp_path, version="1.2.0", url=URL_INSTALADOR, conteudo=INSTALADOR, notes="Melhorias"):
    exe = tmp_path / "setup.exe"
    exe.write_bytes(conteudo)
    return signer.build_manifest(priv, exe, version, url, notes)


def servidor(m, instalador=INSTALADOR, hits=None):
    def handler(req: httpx.Request):
        if hits is not None:
            hits.append(str(req.url))
        if str(req.url) == URL_MANIFESTO:
            return httpx.Response(200, json=m)
        if str(req.url) == URL_INSTALADOR:
            return httpx.Response(200, content=instalador)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


# ---------------- versoes ----------------
@pytest.mark.parametrize("novo,atual,esperado", [("1.2.0", "1.1.9", True), ("2.0.0", "1.99.99", True), ("1.0.0", "1.0.0", False), ("0.9.0", "1.0.0", False),
                                                 ("1.10.0", "1.9.0", True), ("v1.2.0", "1.1.0", True), ("lixo", "1.0.0", False), ("1.2", "1.0.0", False)])
def test_so_versao_mais_nova(novo, atual, esperado):
    assert U.is_newer(novo, atual) is esperado


# ---------------- assinatura ----------------
def test_manifesto_assinado_e_aceito(signer, chaves):
    priv, key, tmp = chaves
    m = U.verify_manifest(manifesto(signer, priv, tmp), key)
    assert m["version"] == "1.2.0" and m["sha256"] == hashlib.sha256(INSTALADOR).hexdigest() and m["size"] == len(INSTALADOR)


@pytest.mark.parametrize("campo,valor", [("version", "9.9.9"), ("url", "https://evil.example/Jefrey-Setup.exe"), ("sha256", "0" * 64), ("size", 2_000_000)])
def test_qualquer_campo_adulterado_quebra_a_assinatura(signer, chaves, campo, valor):
    priv, key, tmp = chaves
    m = manifesto(signer, priv, tmp)
    m[campo] = valor
    with pytest.raises(U.UpdateError, match="assinatura"):
        U.verify_manifest(m, key)


def test_assinatura_de_outra_chave_e_recusada(signer, chaves, tmp_path):
    priv, key, tmp = chaves
    outra = tmp_path / "outra.txt"
    signer.gen_key(outra)
    with pytest.raises(U.UpdateError, match="assinatura"):
        U.verify_manifest(manifesto(signer, outra, tmp), key)


@pytest.mark.parametrize("mexe,msg", [
    (lambda m: m.pop("signature"), "incompleta"), (lambda m: m.update(signature="não é base64!"), "incompleta"),
    (lambda m: m.update(version="abc"), "incompleta"), (lambda m: m.update(sha256="xyz"), "segura"), (lambda m: m.update(size=10), "segura"),
    (lambda m: m.update(size=10**12), "segura"), (lambda m: m.update(url="http://downloads.exemplo.com/a.exe"), "https"),
    (lambda m: m.update(url="https://user:senha@downloads.exemplo.com/a.exe"), "https"), (lambda m: m.update(url="ftp://x/a.exe"), "https"),
])
def test_manifesto_malformado_ou_inseguro(signer, chaves, mexe, msg):
    priv, key, tmp = chaves
    m = manifesto(signer, priv, tmp)
    mexe(m)
    with pytest.raises(U.UpdateError, match=msg):
        U.verify_manifest(m, key)
    for lixo in ("texto", [1, 2], None, 5):
        with pytest.raises(U.UpdateError):
            U.verify_manifest(lixo, key)


def test_sem_chave_publica_nada_e_aceito(signer, chaves, monkeypatch, tmp_path):
    priv, key, tmp = chaves
    monkeypatch.setattr(U, "PUBLIC_KEY_B64", "")
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "vazio"))
    with pytest.raises(U.UpdateError, match="habilitadas"):
        U.verify_manifest(manifesto(signer, priv, tmp))


def test_chave_publica_vem_do_arquivo_de_configuracao(signer, chaves, monkeypatch, tmp_path):
    priv, key, tmp = chaves
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    pub = base64.b64encode(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    (cfg / "update_public_key.txt").write_text(pub, encoding="utf-8")
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(cfg))
    assert U.verify_manifest(manifesto(signer, priv, tmp))["version"] == "1.2.0"
    (cfg / "update_public_key.txt").write_text("lixo", encoding="utf-8")
    with pytest.raises(U.UpdateError, match="habilitadas"):
        U.verify_manifest(manifesto(signer, priv, tmp))


# ---------------- consulta ----------------
def test_consulta_avisa_so_quando_ha_versao_mais_nova(signer, chaves):
    priv, key, tmp = chaves
    m = manifesto(signer, priv, tmp)
    r = run(U.check(transport=servidor(m), key=key, current="1.1.0", url=URL_MANIFESTO))
    assert r == {"current": "1.1.0", "available": True, "enabled": True, "version": "1.2.0", "notes": "Melhorias", "size": len(INSTALADOR)}
    assert run(U.check(transport=servidor(m), key=key, current="1.2.0", url=URL_MANIFESTO))["available"] is False
    assert run(U.check(transport=servidor(m), key=key, current="2.0.0", url=URL_MANIFESTO))["available"] is False  # sem downgrade


def test_consulta_desligada_sem_endereco_e_so_https(signer, chaves, monkeypatch):
    monkeypatch.delenv("JEFREY_UPDATE_URL", raising=False)
    assert run(U.check(current="1.0.0")) == {"current": "1.0.0", "available": False, "enabled": False}
    with pytest.raises(U.UpdateError, match="https"):
        run(U.check(url="http://atualizacoes.exemplo.com/manifest.json", current="1.0.0"))


def test_consulta_com_servidor_fora_ou_resposta_enorme(signer, chaves):
    priv, key, tmp = chaves
    def fora(req):
        raise httpx.ConnectError("sem rede")
    with pytest.raises(U.UpdateError, match="internet"):
        run(U.check(transport=httpx.MockTransport(fora), key=key, current="1.0.0", url=URL_MANIFESTO))
    grande = httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 50_000))
    with pytest.raises(U.UpdateError, match="agora"):
        run(U.check(transport=grande, key=key, current="1.0.0", url=URL_MANIFESTO))
    with pytest.raises(U.UpdateError, match="agora"):
        run(U.check(transport=httpx.MockTransport(lambda r: httpx.Response(503)), key=key, current="1.0.0", url=URL_MANIFESTO))


# ---------------- download ----------------
def test_download_confere_tamanho_e_hash(signer, chaves, tmp_path):
    priv, key, tmp = chaves
    m = U.verify_manifest(manifesto(signer, priv, tmp), key)
    p = run(U.download(m, tmp_path / "dl", transport=servidor(None)))
    assert p.read_bytes() == INSTALADOR


def test_download_adulterado_e_apagado_e_recusado(signer, chaves, tmp_path):
    priv, key, tmp = chaves
    m = U.verify_manifest(manifesto(signer, priv, tmp), key)
    trocado = bytearray(INSTALADOR)
    trocado[100] ^= 0xFF
    with pytest.raises(U.UpdateError, match="não confere"):
        run(U.download(m, tmp_path / "dl", transport=servidor(None, bytes(trocado))))
    assert not (tmp_path / "dl" / "Jefrey-Setup-update.exe").exists()
    with pytest.raises(U.UpdateError, match="maior"):
        run(U.download(m, tmp_path / "dl", transport=servidor(None, INSTALADOR + b"extra")))
    assert not (tmp_path / "dl" / "Jefrey-Setup-update.exe").exists()
    with pytest.raises(U.UpdateError, match="não confere"):
        run(U.download(m, tmp_path / "dl", transport=servidor(None, INSTALADOR[:-1])))


def test_download_nao_aceita_desvio_para_http(signer, chaves, tmp_path):
    priv, key, tmp = chaves
    m = U.verify_manifest(manifesto(signer, priv, tmp), key)

    def handler(req):
        if str(req.url) == URL_INSTALADOR:
            return httpx.Response(302, headers={"location": "http://malicioso.example/a.exe"})
        return httpx.Response(200, content=INSTALADOR)
    with pytest.raises(U.UpdateError):
        run(U.download(m, tmp_path / "dl", transport=httpx.MockTransport(handler)))


# ---------------- instalacao ----------------
def _home(tmp_path):
    h = tmp_path / "home"
    (h / "config").mkdir(parents=True)
    (h / "data").mkdir()
    (h / "data" / "jefrey.db").write_bytes(b"banco")
    (h / "config" / "llm_api_key").write_text("segredo", encoding="utf-8")
    return h


def test_instalar_baixa_confere_faz_backup_e_roda_o_instalador(signer, chaves, tmp_path):
    priv, key, tmp = chaves
    m = manifesto(signer, priv, tmp)
    rodou = []
    home = _home(tmp_path)
    r = run(U.install(transport=servidor(m), key=key, home=home, runner=rodou.append, url=URL_MANIFESTO, current="1.1.0"))
    assert r["started"] is True and r["version"] == "1.2.0" and r["backup"].startswith("jefrey-backup-")
    assert len(rodou) == 1 and rodou[0].read_bytes() == INSTALADOR
    import zipfile
    with zipfile.ZipFile(home / "backups" / r["backup"]) as z:
        nomes = z.namelist()
    assert "data/jefrey.db" in nomes and not any("llm_api_key" in n for n in nomes)  # backup sem chaves


@pytest.mark.parametrize("cenario", ["assinatura", "hash", "mesma_versao", "sem_url", "http"])
def test_instalador_nunca_roda_quando_algo_nao_confere(signer, chaves, tmp_path, cenario):
    priv, key, tmp = chaves
    m = manifesto(signer, priv, tmp)
    rodou, instalador, url, atual = [], INSTALADOR, URL_MANIFESTO, "1.1.0"
    if cenario == "assinatura":
        m["version"] = "9.9.9"
    elif cenario == "hash":
        instalador = bytes(len(INSTALADOR))
    elif cenario == "mesma_versao":
        atual = "1.2.0"
    elif cenario == "sem_url":
        url = ""
    elif cenario == "http":
        url = "http://atualizacoes.exemplo.com/manifest.json"
    with pytest.raises(U.UpdateError):
        run(U.install(transport=servidor(m, instalador), key=key, home=_home(tmp_path), runner=rodou.append, url=url, current=atual))
    assert rodou == []


def test_backup_com_falha_nao_impede_a_atualizacao_mas_e_informado(signer, chaves, tmp_path, monkeypatch):
    priv, key, tmp = chaves
    m = manifesto(signer, priv, tmp)
    monkeypatch.setattr(U, "backup_before_update", lambda home: None)
    rodou = []
    r = run(U.install(transport=servidor(m), key=key, home=tmp_path / "x", runner=rodou.append, url=URL_MANIFESTO, current="1.0.0"))
    assert r["backup"] is None and len(rodou) == 1


def test_o_instalador_so_roda_no_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(U.sys, "platform", "linux")
    with pytest.raises(U.UpdateError, match="Windows"):
        U.run_installer(tmp_path / "x.exe")


# ---------------- API ----------------
@pytest.fixture()
def api():
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    tok = c.post("/auth/dev-token", json={"user_id": "apiupd"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def test_api_exige_login_e_e_segura_por_padrao(api, monkeypatch):
    c, h = api
    assert c.get("/updates/check").status_code == 401 and c.post("/updates/install").status_code == 401
    monkeypatch.delenv("JEFREY_UPDATE_URL", raising=False)
    assert c.get("/updates/check", headers=h).json()["enabled"] is False
    assert c.post("/updates/install", headers=h).status_code == 404  # fora do programa instalado nao instala nada


def test_api_instala_so_no_programa_instalado_e_fecha_para_o_instalador(api, monkeypatch):
    c, h = api
    from src.jefrey.native import control
    fechou = []
    control.set_quit_hook(lambda: fechou.append(1))
    try:
        async def falso_install():
            return {"started": True, "version": "1.2.0", "backup": "b.zip"}
        monkeypatch.setattr(U, "install", falso_install)
        r = c.post("/updates/install", headers=h)
        assert r.status_code == 200 and r.json()["version"] == "1.2.0" and fechou == [1]

        async def recusa():
            raise U.UpdateError("A assinatura da atualização não confere. Não vou instalar.")
        monkeypatch.setattr(U, "install", recusa)
        r2 = c.post("/updates/install", headers=h)
        assert r2.status_code == 409 and "assinatura" in r2.json()["detail"] and fechou == [1]  # recusou: nao fechou o programa
    finally:
        control.set_quit_hook(None)

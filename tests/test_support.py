import asyncio
import io
import json
import zipfile

import pytest
from fastapi import HTTPException

from src.jefrey.core import support as S

SEGREDOS = [
    "sk-proj-AbCdEf1234567890AbCdEf1234567890",
    "gsk_abcdefghijklmnopqrstuvwxyz123456",
    "GOCSPX-abcdefghijklmnop1234",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vIn0.abcdefghijklmnopqrstuvwxyz",
    "meu-token-super-secreto-1234567890",
]


@pytest.fixture()
def casa(tmp_path, monkeypatch):
    (tmp_path / "config" / "credentials").mkdir(parents=True)
    (tmp_path / "config" / "credentials" / "llm_key").write_text(SEGREDOS[0], encoding="utf-8")
    (tmp_path / "config" / "native_secrets.json").write_text(json.dumps({"api_secret": SEGREDOS[4]}), encoding="utf-8")
    (tmp_path / "logs").mkdir()
    linhas = [f"2026-10-05 INFO pedido ok {i}" for i in range(700)]
    linhas += [f"INFO httpx: GET https://x/y?token={SEGREDOS[4]}", f"DEBUG header Authorization: Bearer {SEGREDOS[3]}",
               f'INFO payload {{"api_key": "{SEGREDOS[1]}", "client_secret": "{SEGREDOS[2]}"}}', f"WARN chave {SEGREDOS[0]} recusada"]
    (tmp_path / "logs" / "jefrey.log").write_text("\n".join(linhas), encoding="utf-8")
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "config"))
    return tmp_path


def _zip(b: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(b))


def test_relatorio_nao_contem_nenhum_segredo(casa):
    z = _zip(S.build_report(casa / "logs", casa / "config"))
    todo = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist())
    for s in SEGREDOS:
        assert s not in todo, s[:12]


def test_relatorio_tem_versao_log_recente_e_estado(casa):
    z = _zip(S.build_report(casa / "logs", casa / "config"))
    assert {"info.txt", "jefrey.log", "estado.json"} <= set(z.namelist())
    assert "Versão" in z.read("info.txt").decode("utf-8")
    log = z.read("jefrey.log").decode("utf-8")
    assert log.count("\n") <= S.MAX_LINES and "pedido ok 699" in log and "pedido ok 0" not in log  # so o final


def test_relatorio_nunca_inclui_cofre_nem_arquivos_de_segredo(casa):
    nomes = _zip(S.build_report(casa / "logs", casa / "config")).namelist()
    assert not [n for n in nomes if "secret" in n.lower() or "credential" in n.lower() or "llm_key" in n or n.endswith(".json") and n != "estado.json"]


def test_estado_so_tem_sim_ou_nao_nunca_valores(casa):
    estado = json.loads(_zip(S.build_report(casa / "logs", casa / "config")).read("estado.json"))
    assert all(isinstance(v, (bool, int, str, list)) for v in estado.values())
    assert "sk-" not in json.dumps(estado)


def test_sem_log_ainda_gera_relatorio(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "config"))
    z = _zip(S.build_report(tmp_path / "logs-nao-existe", tmp_path / "config"))
    assert "info.txt" in z.namelist()


def test_rota_salva_em_documentos_e_exige_login(casa, monkeypatch, tmp_path):
    from src.jefrey.api import support_routes as R

    class Req:
        def __init__(self, uid):
            self.state = type("S", (), {"user_id": uid})()
    with pytest.raises(HTTPException) as e:
        asyncio.run(R.report(Req(None)))
    assert e.value.status_code == 401
    monkeypatch.setattr(S.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Documents").mkdir()
    monkeypatch.setattr(R, "_open_folder", lambda p: None)
    out = asyncio.run(R.report(Req("ana")))
    assert out["ok"] is True and out["path"].endswith(".zip") and (tmp_path / "Documents" / "Jefrey" / "relatorios").is_dir()
    assert _zip((tmp_path / "Documents" / "Jefrey" / "relatorios" / out["path"].split("\\")[-1].split("/")[-1]).read_bytes()).namelist()

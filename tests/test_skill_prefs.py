"""Ligar/desligar skills: persistencia, validacao, API e efeito nas ferramentas do agente."""
import json

import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app
from src.jefrey.core.skill_prefs import enabled_tools, load_disabled, set_enabled


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_padrao_nada_desligado(cfg):
    assert load_disabled() == set()


def test_desligar_e_religar_persistem(cfg):
    set_enabled("drive", False)
    set_enabled("email", False)
    assert load_disabled() == {"drive", "email"}
    assert json.loads((cfg / "skills.runtime.json").read_text(encoding="utf-8"))["disabled"] == ["drive", "email"]
    set_enabled("drive", True)
    assert load_disabled() == {"email"}


@pytest.mark.parametrize("bad", ["", "../x", "A B", "x" * 80, "Drive", "1abc", "a;b"])
def test_nome_invalido_e_recusado(cfg, bad):
    with pytest.raises(ValueError):
        set_enabled(bad, False)


def test_arquivo_corrompido_vira_padrao_sem_quebrar(cfg):
    (cfg / "skills.runtime.json").write_text("{nao e json", encoding="utf-8")
    assert load_disabled() == set()
    (cfg / "skills.runtime.json").write_text(json.dumps({"disabled": ["ok_skill", 5, "../x"]}), encoding="utf-8")
    assert load_disabled() == {"ok_skill"}


def test_gravacao_nao_deixa_arquivo_temporario(cfg):
    set_enabled("drive", False)
    assert [p.name for p in cfg.iterdir()] == ["skills.runtime.json"]


class _Tool:
    def __init__(self, name):
        self.name = name


class _Skill:
    def __init__(self, name, tools):
        self.metadata = type("M", (), {"name": name})()
        self._t = tools

    def get_tools(self):
        return [_Tool(t) for t in self._t]


def test_agente_so_enxerga_ferramentas_de_skills_ligadas_e_classificadas(cfg):
    skills = [_Skill("notes", ["save_note", "sem_catalogo"]), _Skill("drive", ["list_files"])]
    catalog = {"save_note": 1, "list_files": 1}
    assert set(enabled_tools(skills, catalog)) == {"save_note", "list_files"}
    set_enabled("drive", False)
    assert set(enabled_tools(skills, catalog)) == {"save_note"}


# ---------------- API ----------------
@pytest.fixture()
def client(cfg):
    return TestClient(app)


def _h(client):
    return {"Authorization": f"Bearer {client.post('/auth/dev-token').json()['access_token']}"}


def test_api_exige_login(client):
    assert client.put("/skills/notes", json={"enabled": False}).status_code == 401


def test_api_desliga_e_lista_estado(client):
    h = _h(client)
    assert client.put("/skills/essentials", headers=h, json={"enabled": False}).json() == {"name": "essentials", "enabled": False}
    skills = {s["name"]: s["enabled"] for s in client.get("/skills", headers=h).json()["skills"]}
    assert skills["essentials"] is False and skills["notes"] is True
    client.put("/skills/essentials", headers=h, json={"enabled": True})
    again = {s["name"]: s["enabled"] for s in client.get("/skills", headers=h).json()["skills"]}
    assert again["essentials"] is True


def test_api_skill_inexistente_404_e_corpo_invalido_422(client):
    h = _h(client)
    assert client.put("/skills/nao_existe", headers=h, json={"enabled": False}).status_code == 404
    assert client.put("/skills/notes", headers=h, json={"enabled": "talvez"}).status_code == 422
    assert load_disabled() == set()

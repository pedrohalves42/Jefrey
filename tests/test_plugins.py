"""Plugins: so carrega o que a pessoa aprovou pelo hash; mudou depois, bloqueia de novo; ferramenta de plugin e risco alto."""
import pytest

from src.jefrey.adapters.outbound.plugin_env import mark_high_risk, tool_names
from src.jefrey.application.plugins import PluginStore
from src.jefrey.domain.tool_catalog import CATALOG

CODIGO = '''
from src.jefrey.skills import SkillBase, SkillMetadata, tool
class Ola(SkillBase):
    metadata = SkillMetadata(name="plug_ola", description="plugin de teste")
    def initialize(self): return True
    def get_tools(self): return [self.plug_diga_ola]
    @tool(description="diz ola")
    async def plug_diga_ola(self) -> str:
        return "ola"
from src.jefrey.skills import skill_registry
skill_registry.register(Ola())
'''


@pytest.fixture
def store(tmp_path):
    d = tmp_path / "plugins"
    d.mkdir()
    (d / "ola.py").write_text(CODIGO, encoding="utf-8")
    return PluginStore(d, tmp_path / "ap.json", tool_names, mark_high_risk)


def test_arquivo_novo_nao_carrega(store):
    assert store.scan()[0]["state"] == "novo"
    assert store.load_approved() == []


def test_aprovar_com_hash_errado_nao_vale(store):
    assert store.approve("ola", "0" * 64) is False
    assert store.scan()[0]["state"] == "novo"


def test_aprovado_carrega_e_ferramenta_vira_risco_alto(store):
    h = store.scan()[0]["sha256"]
    assert store.approve("ola", h) is True
    assert store.load_approved() == ["ola"]
    assert CATALOG["plug_diga_ola"].needs_approval is True


def test_alterado_depois_da_aprovacao_bloqueia(store, tmp_path):
    store.approve("ola", store.scan()[0]["sha256"])
    (tmp_path / "plugins" / "ola.py").write_text(CODIGO + "\n# mexeram", encoding="utf-8")
    assert store.scan()[0]["state"] == "alterado"
    assert store.load_approved() == []


def test_revogar_bloqueia(store):
    store.approve("ola", store.scan()[0]["sha256"])
    assert store.revoke("ola") is True
    assert store.scan()[0]["state"] == "novo"


def test_nome_estranho_e_ignorado(store, tmp_path):
    (tmp_path / "plugins" / "Mau-Nome.py").write_text("x=1", encoding="utf-8")
    assert [i["name"] for i in store.scan()] == ["ola"]


def test_plugin_com_erro_nao_derruba(store, tmp_path):
    (tmp_path / "plugins" / "quebrado.py").write_text("raise RuntimeError('x')", encoding="utf-8")
    for i in store.scan():
        store.approve(i["name"], i["sha256"])
    assert "quebrado" not in store.load_approved()

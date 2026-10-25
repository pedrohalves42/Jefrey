"""Tarefa 1 (B): o esquema enviado ao modelo fica menor sem perder nome, tipo, campo ou obrigatoriedade."""
from pydantic import BaseModel, Field

from src.jefrey.application.tool_runtime import compact_spec, tool_spec


class Args(BaseModel):
    titulo: str = Field(..., description="texto longo " * 20, examples=["exemplo"])
    quando: str = Field("hoje", description="data " * 30)
    repetir: bool = False


class Fake:
    name = "criar_coisa"
    description = "Cria uma coisa na agenda. " + "detalhe " * 60
    args_schema = Args


def test_compacto_mantem_nome_tipos_e_obrigatorios():
    spec = compact_spec(tool_spec(Fake()))
    props = spec["parameters"]["properties"]
    assert spec["name"] == "criar_coisa"
    assert set(props) == {"titulo", "quando", "repetir"}
    assert props["titulo"]["type"] == "string" and props["repetir"]["type"] == "boolean"
    assert spec["parameters"]["required"] == ["titulo"]


def test_compacto_corta_descricoes_e_tira_o_peso_extra():
    cheio = tool_spec(Fake())
    leve = compact_spec(cheio)
    assert len(leve["description"]) <= 120
    assert "description" not in leve["parameters"]["properties"]["titulo"]
    assert "examples" not in leve["parameters"]["properties"]["titulo"]
    assert len(str(leve)) < len(str(cheio)) * 0.6

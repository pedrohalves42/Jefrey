"""Ferramentas essenciais: calculadora segura, arquivos isolados por usuario, hora, clima."""
import asyncio

import httpx
import pytest

from src.jefrey.skills import essentials as ess
from src.jefrey.skills.essentials import CalcError, EssentialsSkill, safe_eval


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def skill():
    return EssentialsSkill()


@pytest.fixture(autouse=True)
def files_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_FILES_DIR", str(tmp_path / "files"))
    return tmp_path / "files"


def call(skill, name, **kw):
    """Chama a ferramenta como o runtime faz (StructuredTool.ainvoke)."""
    tool = getattr(skill, name)
    return run(tool.ainvoke(kw))


# ---------------- calculadora ----------------
@pytest.mark.parametrize("expr,expected", [
    ("17*23", 391), ("2+2", 4), ("10/4", 2.5), ("2**10", 1024), ("(1+2)*3", 9), ("-5+2", -3),
    ("17 × 23", 391), ("10 ÷ 4", 2.5), ("2^3", 8), ("1,5+1", 2.5), ("sqrt(16)", 4), ("round(2.567, 1)", 2.6),
    ("10 % 3", 1), ("7 // 2", 3), ("pi", 3.1415926536),
])
def test_calculos_validos(expr, expected):
    assert safe_eval(expr) == pytest.approx(expected)


@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo oi')", "open('x')", "().__class__", "a+1", "'a'*3", "[1,2]", "lambda: 1",
    "1/0", "2**99999", "", "   ", "sqrt(-1)", "x" * 300, "exec('1')", "True+1", "abs(1,2,3)", "print(1)",
])
def test_expressoes_perigosas_ou_invalidas_sao_recusadas(expr):
    with pytest.raises(CalcError):
        safe_eval(expr)


def test_ferramenta_calculadora_nao_levanta_erro(skill):
    assert call(skill, "calculator", expression="17*23") == "17*23 = 391"
    assert "Nao consegui calcular" in call(skill, "calculator", expression="__import__('os')")


# ---------------- arquivos ----------------
def test_gravar_ler_e_listar(skill):
    assert "gravado" in call(skill, "files_write", path="notas/mercado.txt", content="leite", user_id="ana")
    assert call(skill, "files_read", path="notas/mercado.txt", user_id="ana") == "leite"
    assert "mercado.txt" in call(skill, "files_list", folder="notas", user_id="ana")
    assert "[pasta] notas" in call(skill, "files_list", user_id="ana")


@pytest.mark.parametrize("bad", ["../outro/segredo.txt", "../../etc/passwd", "a/../../x",
                                 "..\\..\\windows\\system32", ""])
def test_nao_sai_da_pasta_do_usuario(skill, bad):
    out = call(skill, "files_read", path=bad, user_id="ana")
    assert "Nao permitido" in out or "nao existe" in out
    assert "root:" not in out
    out = call(skill, "files_write", path=bad, content="x", user_id="ana")
    assert "Nao permitido" in out


def test_usuarios_nao_enxergam_arquivos_um_do_outro(skill):
    call(skill, "files_write", path="segredo.txt", content="da ana", user_id="ana")
    assert "nao existe" in call(skill, "files_read", path="segredo.txt", user_id="bob")
    assert "segredo.txt" not in call(skill, "files_list", user_id="bob")


def test_user_id_malicioso_nao_escapa(skill, files_dir):
    call(skill, "files_write", path="a.txt", content="x", user_id="../../fora")
    created = [p for p in files_dir.rglob("a.txt")]
    assert len(created) == 1 and files_dir in created[0].parents


def test_limites_de_tamanho(skill):
    assert "grande demais" in call(skill, "files_write", path="g.txt", content="a" * 300_000, user_id="ana")
    call(skill, "files_write", path="m.txt", content="a" * 150_000, user_id="ana")
    out = call(skill, "files_read", path="m.txt", user_id="ana")
    assert len(out) < 100_100 and "cortado" in out


# ---------------- hora ----------------
def test_hora_em_portugues(skill):
    out = call(skill, "current_time")
    assert any(d in out for d in ess.WEEKDAYS) and any(m in out for m in ess.MONTHS)


def test_fuso_invalido_cai_no_local(skill):
    assert any(d in call(skill, "current_time", timezone="Marte/Cratera") for d in ess.WEEKDAYS)


# ---------------- clima (rede simulada) ----------------
def test_clima_com_resposta_simulada(skill, monkeypatch):
    def handler(req):
        if "geocoding" in str(req.url):
            return httpx.Response(200, json={"results": [{"name": "Recife", "admin1": "Pernambuco", "country": "Brasil",
                                                          "latitude": -8.0, "longitude": -34.9}]})
        return httpx.Response(200, json={"current": {"temperature_2m": 28.5, "apparent_temperature": 31,
                                                     "relative_humidity_2m": 70, "wind_speed_10m": 12, "precipitation": 0}})
    real = httpx.AsyncClient
    monkeypatch.setattr(__import__("httpx"), "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    out = call(skill, "weather", city="Recife")
    assert "Recife" in out and "28,5" in out


def test_clima_sem_internet_nao_levanta(skill, monkeypatch):
    def boom(req):
        raise httpx.ConnectError("sem rede")
    real = httpx.AsyncClient
    monkeypatch.setattr(__import__("httpx"), "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(boom), **kw))
    assert "Nao consegui consultar" in call(skill, "weather", city="Recife")


def test_clima_cidade_vazia(skill):
    assert "cidade" in call(skill, "weather", city="  ")


def test_caminho_absoluto_fica_confinado_na_pasta_do_usuario(skill, files_dir):
    """"/etc/passwd" vira "<pasta do usuario>/etc/passwd": nunca toca o arquivo real do sistema."""
    call(skill, "files_write", path="/tmp/teste-jefrey-confinado.txt", content="x", user_id="ana")
    created = list(files_dir.rglob("teste-jefrey-confinado.txt"))
    assert len(created) == 1 and files_dir in created[0].parents
    assert "root:" not in call(skill, "files_read", path="/etc/passwd", user_id="ana")

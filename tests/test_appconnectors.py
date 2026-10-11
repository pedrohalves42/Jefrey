import ast
import asyncio
import json
from pathlib import Path

import pytest

from src.jefrey.core.appconnectors import ConnectorError, run_command
from src.jefrey.core.appconnectors import blender as B

ROOT = Path(__file__).resolve().parents[1]


def run(c):
    return asyncio.run(c)


def test_comando_fora_da_lista_e_recusado():
    for c in ("run_python", "exec", "open_file", "save_as", "import_addon", "__import__"):
        with pytest.raises(ConnectorError, match="(?i)não conheço"):
            B.validate(c, {})


def test_argumentos_validados():
    assert B.validate("add_cube", {"x": 1, "y": 2, "z": 3, "size": 2})["args"] == {"x": 1.0, "y": 2.0, "z": 3.0, "size": 2.0, "name": ""}
    assert B.validate("move_object", {"name": "Cube", "x": 0, "y": 0, "z": 5})["args"]["name"] == "Cube"
    assert B.validate("set_color", {"name": "Cube", "r": 1, "g": 0, "b": 0})["args"]["r"] == 1.0
    for bad in [{"x": 99999}, {"x": "um"}, {"size": 0}, {"size": 1000}, {"name": "a" * 41}, {"name": "Cube; import os"}, {"x": float("nan")}]:
        with pytest.raises(ConnectorError):
            B.validate("add_cube", bad)
    with pytest.raises(ConnectorError, match="nome"):
        B.validate("delete_object", {})
    with pytest.raises(ConnectorError):
        B.validate("add_cube", {"extra": 1})  # argumento desconhecido


def test_so_aceita_127_0_0_1():
    assert B.HOST == "127.0.0.1"
    assert "0.0.0.0" not in Path(B.__file__).read_text(encoding="utf-8")


def test_sem_token_ou_sem_blender_explica(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "token_file", lambda: tmp_path / "nao-existe")
    with pytest.raises(ConnectorError, match="Blender"):
        run(B.send({"command": "add_cube", "args": {}}))


def test_ida_e_volta_com_servidor_falso(tmp_path, monkeypatch):
    tok = tmp_path / "token"
    tok.write_text("segredo-de-teste-123", encoding="utf-8")
    monkeypatch.setattr(B, "token_file", lambda: tok)
    recebido = {}

    async def handler(reader, writer):
        recebido.update(json.loads((await reader.readline()).decode()))
        writer.write((json.dumps({"ok": True, "message": "Cubo criado."}) + "\n").encode())
        await writer.drain()
        writer.close()

    async def fluxo():
        srv = await asyncio.start_server(handler, "127.0.0.1", 0)
        monkeypatch.setattr(B, "PORT", srv.sockets[0].getsockname()[1])
        async with srv:
            return await run_command("blender", "add_cube", {"x": 1})
    out = run(fluxo())
    assert out == "Cubo criado." and recebido["token"] == "segredo-de-teste-123" and recebido["command"] == "add_cube"


def test_erro_do_blender_vira_frase(tmp_path, monkeypatch):
    tok = tmp_path / "token"
    tok.write_text("t" * 20, encoding="utf-8")
    monkeypatch.setattr(B, "token_file", lambda: tok)

    async def handler(reader, writer):
        await reader.readline()
        writer.write((json.dumps({"ok": False, "message": "Não achei o objeto Cube."}) + "\n").encode())
        await writer.drain()
        writer.close()

    async def fluxo():
        srv = await asyncio.start_server(handler, "127.0.0.1", 0)
        monkeypatch.setattr(B, "PORT", srv.sockets[0].getsockname()[1])
        async with srv:
            return await run_command("blender", "delete_object", {"name": "Cube"})
    with pytest.raises(ConnectorError, match="Não achei"):
        run(fluxo())


def test_programa_desconhecido():
    with pytest.raises(ConnectorError, match="(?i)não conheço"):
        run(run_command("photoshop", "add_cube", {}))


def _addon():
    return (ROOT / "extensions" / "blender" / "jefrey_addon.py").read_text(encoding="utf-8")


def test_addon_so_tem_os_mesmos_comandos_e_nada_perigoso():
    tree = ast.parse(_addon())
    allowed = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "ALLOWED" for t in n.targets):
            allowed = set(ast.literal_eval(n.value))
    assert allowed == set(B.COMMANDS)
    src = _addon()
    import re
    for proibido in ("eval(", "exec(", "os.system", "subprocess", "__import__", "0.0.0.0"):
        assert proibido not in src, proibido
    assert not re.search(r"(?<!re\.)compile\(", src)  # compile() do Python, nao re.compile
    assert "127.0.0.1" in src and "hmac.compare_digest" in src

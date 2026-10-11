"""Conector do Blender: fala com o add-on `extensions/blender/jefrey_addon.py` por um soquete LOCAL (127.0.0.1) com token.

Comandos: so os de COMMANDS. O add-on repete a mesma lista e a mesma validacao; nenhum dos dois executa texto livre.
O token e gerado pelo add-on e guardado em ~/.jefrey_blender/token (so este usuario do Windows).
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path

from src.jefrey.adapters.outbound.appconnectors import ConnectorError

HOST = "127.0.0.1"
PORT = 8765
TIMEOUT = 10.0
_NAME = re.compile(r"[A-Za-z0-9_. -]{1,40}")
_COORD = (-1000.0, 1000.0)

# comando -> argumentos aceitos (nome -> (tipo, minimo, maximo, padrao)); "name" e texto, "name!" e texto obrigatorio
COMMANDS: dict[str, dict[str, tuple]] = {
    "add_cube": {"name": ("name", None, None, ""), "x": ("num", *_COORD, 0.0), "y": ("num", *_COORD, 0.0), "z": ("num", *_COORD, 0.0), "size": ("num", 0.01, 100.0, 2.0)},
    "add_sphere": {"name": ("name", None, None, ""), "x": ("num", *_COORD, 0.0), "y": ("num", *_COORD, 0.0), "z": ("num", *_COORD, 0.0), "size": ("num", 0.01, 100.0, 1.0)},
    "move_object": {"name": ("name!", None, None, None), "x": ("num", *_COORD, 0.0), "y": ("num", *_COORD, 0.0), "z": ("num", *_COORD, 0.0)},
    "delete_object": {"name": ("name!", None, None, None)},
    "set_color": {"name": ("name!", None, None, None), "r": ("num", 0.0, 1.0, 0.8), "g": ("num", 0.0, 1.0, 0.8), "b": ("num", 0.0, 1.0, 0.8)},
}


def token_file() -> Path:
    return Path.home() / ".jefrey_blender" / "token"


def validate(command: str, args: dict) -> dict:
    spec = COMMANDS.get((command or "").strip())
    if spec is None:
        raise ConnectorError("Não conheço esse comando do Blender. Eu sei: " + ", ".join(sorted(COMMANDS)) + ".")
    extra = set(args) - set(spec)
    if extra:
        raise ConnectorError("Argumento desconhecido: " + ", ".join(sorted(extra)) + ".")
    out: dict = {}
    for key, (kind, lo, hi, default) in spec.items():
        v = args.get(key, default)
        if kind.startswith("name"):
            if v in (None, "") and kind.endswith("!"):
                raise ConnectorError("Diga o nome do objeto.")
            if v and not _NAME.fullmatch(str(v)):
                raise ConnectorError("O nome do objeto só pode ter letras, números, espaço, ponto, traço e até 40 caracteres.")
            out[key] = str(v or "")
        else:
            try:
                f = float(v)
            except (TypeError, ValueError):
                raise ConnectorError(f"O valor de {key} precisa ser um número.")
            if math.isnan(f) or math.isinf(f) or not lo <= f <= hi:
                raise ConnectorError(f"O valor de {key} precisa estar entre {lo:g} e {hi:g}.")
            out[key] = f
    return {"command": command.strip(), "args": out}


async def send(payload: dict) -> str:
    try:
        token = token_file().read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    if not token:
        raise ConnectorError("O Blender ainda não está ligado ao Jefrey. Abra o Blender e ative o add-on “Jefrey”.")
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(HOST, PORT), timeout=3)
    except (OSError, asyncio.TimeoutError):
        raise ConnectorError("Não consegui falar com o Blender. Ele está aberto com o add-on “Jefrey” ligado?")
    try:
        writer.write((json.dumps({**payload, "token": token}) + "\n").encode("utf-8"))
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=TIMEOUT)
        resp = json.loads(line.decode("utf-8"))
    except (OSError, asyncio.TimeoutError, ValueError):
        raise ConnectorError("O Blender não respondeu a tempo.")
    finally:
        writer.close()
    if not resp.get("ok"):
        raise ConnectorError(str(resp.get("message") or "O Blender não conseguiu fazer isso.")[:200])
    return str(resp.get("message") or "Pronto.")[:200]

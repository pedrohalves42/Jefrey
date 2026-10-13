bl_info = {
    "name": "Jefrey",
    "author": "Jefrey",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "description": "Deixa o Jefrey criar e mexer em objetos simples por voz (lista fechada de comandos, so neste computador).",
    "category": "Interface",
}

import hmac
import json
import math
import re
import secrets
import socket
import threading
from pathlib import Path

import bpy

HOST = "127.0.0.1"  # nunca expor na rede
PORT = 8765
ALLOWED = ("add_cube", "add_sphere", "move_object", "delete_object", "set_color")
_NAME = re.compile(r"[A-Za-z0-9_. -]{1,40}")
_RANGE = {"x": (-1000.0, 1000.0), "y": (-1000.0, 1000.0), "z": (-1000.0, 1000.0), "size": (0.01, 100.0), "r": (0.0, 1.0), "g": (0.0, 1.0), "b": (0.0, 1.0)}
_TOKEN_FILE = Path.home() / ".jefrey_blender" / "token"

_queue: list = []
_lock = threading.Lock()
_server = None
_token = ""


def _num(args, key, default):
    v = float(args.get(key, default))
    lo, hi = _RANGE[key]
    if math.isnan(v) or not lo <= v <= hi:
        raise ValueError(f"{key} fora do limite")
    return v


def _name(args, required):
    n = str(args.get("name", "") or "")
    if required and not n:
        raise ValueError("Diga o nome do objeto.")
    if n and not _NAME.fullmatch(n):
        raise ValueError("Nome de objeto invalido.")
    return n


def _run(command, args):
    """Roda NA THREAD PRINCIPAL do Blender. Nenhum texto vindo de fora e executado como codigo."""
    if command not in ALLOWED:
        raise ValueError("Comando desconhecido.")
    if command in ("add_cube", "add_sphere"):
        loc = (_num(args, "x", 0), _num(args, "y", 0), _num(args, "z", 0))
        size = _num(args, "size", 2 if command == "add_cube" else 1)
        if command == "add_cube":
            bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=size, location=loc)
        obj = bpy.context.active_object
        n = _name(args, False)
        if n:
            obj.name = n
        return f"Criei {obj.name}."
    obj = bpy.data.objects.get(_name(args, True))
    if obj is None:
        raise ValueError("Não achei esse objeto.")
    if command == "move_object":
        obj.location = (_num(args, "x", obj.location.x), _num(args, "y", obj.location.y), _num(args, "z", obj.location.z))
        return f"Movi {obj.name}."
    if command == "delete_object":
        nome = obj.name
        bpy.data.objects.remove(obj, do_unlink=True)
        return f"Apaguei {nome}."
    mat = bpy.data.materials.new(name="Jefrey")
    mat.diffuse_color = (_num(args, "r", 0.8), _num(args, "g", 0.8), _num(args, "b", 0.8), 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return f"Pintei {obj.name}."


def _tick():
    with _lock:
        jobs = list(_queue)
        _queue.clear()
    for cmd, args, box, done in jobs:
        try:
            box.update(ok=True, message=_run(cmd, args))
        except Exception as e:
            box.update(ok=False, message=str(e)[:200])
        done.set()
    return 0.1 if _server is not None else None


def _handle(conn):
    try:
        conn.settimeout(10)
        data = b""
        while not data.endswith(b"\n") and len(data) < 4096:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk
        msg = json.loads(data.decode("utf-8"))
        if not hmac.compare_digest(str(msg.get("token", "")), _token):
            resp = {"ok": False, "message": "Token invalido."}
        elif msg.get("command") not in ALLOWED:
            resp = {"ok": False, "message": "Comando desconhecido."}
        else:
            box, done = {}, threading.Event()
            with _lock:
                _queue.append((msg["command"], msg.get("args") or {}, box, done))
            resp = box if done.wait(8) and box else {"ok": False, "message": "O Blender demorou demais."}
        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
    except Exception:
        pass
    finally:
        conn.close()


def _serve():
    while _server is not None:
        try:
            conn, _addr = _server.accept()
        except OSError:
            break
        threading.Thread(target=_handle, args=(conn,), daemon=True).start()


def register():
    global _server, _token
    _token = secrets.token_urlsafe(24)
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(_token, encoding="utf-8")
    _server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server.bind((HOST, PORT))
    _server.listen(4)
    threading.Thread(target=_serve, daemon=True).start()
    bpy.app.timers.register(_tick, persistent=True)


def unregister():
    global _server
    s, _server = _server, None
    if s is not None:
        s.close()
    try:
        _TOKEN_FILE.unlink()
    except OSError:
        pass

"""Liga o celular ao programa real: descobre o IP da rede de casa, sobe/derruba o servidor do celular e repassa perguntas ao Jefrey.

O servidor do celular escuta SO no IP privado da rede local (nunca em 0.0.0.0, nunca na internet) e nasce DESLIGADO:
a pessoa liga em Configuracoes. A API principal segue em 127.0.0.1.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from typing import Optional

import httpx

from src.jefrey.domain.pairing import PairingBook, is_private_ip

logger = logging.getLogger(__name__)

PHONE_PORT = 8765
ASK_TIMEOUT_S = 90.0


def lan_ip() -> Optional[str]:
    """IP desta maquina na rede local (sem mandar nenhum pacote). None se nao ha rede privada."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # UDP: so escolhe a interface, nada sai
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip if is_private_ip(ip) and not ip.startswith("127.") else None


async def relay(user_id: str, text: str) -> str:
    """Pergunta ao Jefrey (pela API local, como a propria pessoa) e junta a resposta."""
    base = f"http://127.0.0.1:{os.getenv('JEFREY_API_PORT', '8000')}"
    async with httpx.AsyncClient(base_url=base, timeout=ASK_TIMEOUT_S) as c:
        tok = (await c.post("/auth/dev-token", json={"user_id": user_id})).json()["access_token"]
        h = {"Authorization": "Bearer " + tok}
        answer, pending = "", False
        async with c.stream("POST", "/chat/stream", headers=h, json={"message": text, "thread_id": "phone-" + user_id}) as r:
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:])
                except ValueError:
                    continue
                if ev.get("type") == "token":
                    answer += ev.get("content", "")
                elif ev.get("type") == "pending_approval":
                    pending = True
        if pending:
            answer = (answer + "\n\n" if answer else "") + "Isso precisa da sua aprovação no computador."
        return answer.strip() or "Não tenho uma resposta agora."


class PhoneService:
    def __init__(self, app_factory=None) -> None:
        self._app_factory = app_factory  # (book, relay, enabled) -> app ASGI; entra de fora para este modulo nao conhecer a API
        self.book = PairingBook(now=time.time)
        self.enabled = False
        self.ip: Optional[str] = None
        self._server = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        if self.enabled:
            return True
        ip = lan_ip()
        if ip is None:
            return False
        import uvicorn

        if self._app_factory is None:
            return False
        app = self._app_factory(self.book, relay, lambda: self.enabled)
        self._server = uvicorn.Server(uvicorn.Config(app, host=ip, port=PHONE_PORT, log_level="warning", access_log=False))
        self._thread = threading.Thread(target=self._server.run, name="jefrey-celular", daemon=True)
        self.ip, self.enabled = ip, True
        self._thread.start()
        return True

    def stop(self) -> None:
        self.enabled = False
        self.book.revoke_all()  # desligou: ninguem continua pareado
        if self._server is not None:
            self._server.should_exit = True
        self._server, self._thread = None, None

    def url(self) -> Optional[str]:
        return f"http://{self.ip}:{PHONE_PORT}" if self.enabled and self.ip else None


def qr_svg(text: str) -> str:
    import segno

    return segno.make(text, error="m").svg_inline(scale=6, dark="#000", light="#fff", border=2)

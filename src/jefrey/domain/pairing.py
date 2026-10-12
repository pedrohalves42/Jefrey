"""Pareamento do celular (REGRAS PURAS): codigo de uso unico com validade curta e sessao por aparelho.

- O codigo vale 5 minutos e UMA vez; depois de usado ou vencido e recusado.
- Erros seguidos bloqueiam novas tentativas por um tempo (ninguem adivinha um codigo).
- O que fica guardado e so o HASH do codigo e da sessao: um arquivo vazado nao deixa entrar.
- Cada aparelho pareado pode ser revogado; no maximo MAX_DEVICES ao mesmo tempo.
O relogio e o gerador de segredos entram por parametro, para o teste ser exato.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
from dataclasses import dataclass, field
from typing import Callable, Optional

CODE_TTL_S = 300.0
SESSION_TTL_S = 30 * 24 * 3600.0
MAX_DEVICES = 5
MAX_FAILS = 5
LOCK_S = 300.0


def _h(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_private_ip(ip: str) -> bool:
    """So rede de casa/escritorio (10.x, 172.16-31.x, 192.168.x) ou o proprio computador. Internet e link-local: nao."""
    try:
        a = ipaddress.ip_address((ip or "").strip().strip("[]"))
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    if a.is_loopback:
        return True
    if a.version == 6:
        return a in ipaddress.ip_network("fc00::/7")  # so enderecos locais unicos; faixas de documentacao nao
    return bool(a.is_private and not a.is_link_local and not a.is_unspecified)


def host_is_ip_literal(host_header: str) -> bool:
    """O celular abre pelo IP (http://192.168.0.5:8765). Nome de dominio e recusado: fecha a porta do DNS rebinding."""
    host = (host_header or "").strip()
    if host.startswith("["):
        host = host[1:host.find("]")] if "]" in host else host
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


@dataclass
class Device:
    id: str
    name: str
    user_id: str
    token_hash: str
    created: float
    expires: float


@dataclass
class PairingBook:
    now: Callable[[], float]
    code_gen: Callable[[], str] = lambda: "".join(secrets.choice("0123456789") for _ in range(8))
    token_gen: Callable[[], str] = lambda: secrets.token_urlsafe(32)
    _codes: dict = field(default_factory=dict)  # hash -> (user_id, expira)
    _devices: dict = field(default_factory=dict)  # id -> Device
    _fails: int = 0
    _locked_until: float = 0.0

    def issue_code(self, user_id: str) -> tuple[str, float]:
        """Gera um codigo novo (o anterior deixa de valer). Devolve (codigo, segundos de validade)."""
        self._codes.clear()
        code = self.code_gen()
        self._codes[_h(code)] = (user_id, self.now() + CODE_TTL_S)
        return code, CODE_TTL_S

    def redeem(self, code: str, device_name: str = "Celular") -> Optional[str]:
        """Troca o codigo por uma sessao. Devolve o token, ou None (usado, vencido, errado, bloqueado ou lotado)."""
        t = self.now()
        if t < self._locked_until:
            return None
        key = _h((code or "").strip())
        found = None
        for k, v in list(self._codes.items()):
            if hmac.compare_digest(k, key):
                found = (k, v)
        if found is None or found[1][1] < t:
            self._codes.pop(found[0], None) if found else None
            self._fails += 1
            if self._fails >= MAX_FAILS:
                self._locked_until, self._fails = t + LOCK_S, 0
            return None
        if len(self._devices) >= MAX_DEVICES:
            return None
        del self._codes[found[0]]  # uso unico
        self._fails = 0
        token = self.token_gen()
        dev = Device(id=_h(token)[:12], name=(device_name or "Celular")[:40], user_id=found[1][0],
                     token_hash=_h(token), created=t, expires=t + SESSION_TTL_S)
        self._devices[dev.id] = dev
        return token

    def check(self, token: str) -> Optional[Device]:
        h = _h(token or "")
        t = self.now()
        for d in list(self._devices.values()):
            if d.expires < t:
                del self._devices[d.id]
            elif hmac.compare_digest(d.token_hash, h):
                return d
        return None

    def devices(self) -> list[dict]:
        return [{"id": d.id, "name": d.name, "created": d.created} for d in self._devices.values()]

    def revoke(self, device_id: str) -> bool:
        return self._devices.pop(device_id, None) is not None

    def revoke_all(self) -> None:
        self._devices.clear()
        self._codes.clear()

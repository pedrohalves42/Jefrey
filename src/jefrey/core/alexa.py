"""Alexa: o Jefrey fala nos seus Echo e aciona rotinas, por meio do Voice Monkey (ponte para a Alexa).

A Alexa nao tem uma API para um programa de computador mandar "falar" em um Echo. O Voice Monkey (servico de terceiros) e a ponte:
a pessoa cria uma conta, liga a skill dele no app Alexa, cria "monkeys" (dispositivos) e cola aqui o token. Entao:
- alexa_say: o Echo fala um aviso (ex.: "o jantar esta pronto");
- alexa_routine: aciona uma rotina da Alexa (luzes, tomadas...). E acao com efeito real: pede a aprovacao da pessoa.

ATENCAO: o endereco e os parametros do Voice Monkey seguem o que foi documentado, mas NAO foram testados com uma conta real
(sem acesso aqui). O endereco da API e FIXO (nunca configuravel) para a chave nao ser desviada; o token fica protegido pelo
Windows e nunca aparece em registro nem volta para a tela.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from src.jefrey.core import logredact
from src.jefrey.core.learning import has_secret
from src.jefrey.core.secret_store import read_secret, write_secret

logger = logging.getLogger(__name__)
logredact.install()

BASE = "https://api-v2.voicemonkey.io"
MAX_TEXT = 250
MAX_DEVICES = 12
_NAME = re.compile(r"^[A-Za-zÀ-ÿ0-9 _-]{1,30}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{2,60}$")


class AlexaError(Exception):
    """Mensagem pronta para a tela (portugues simples)."""


def _dir() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config"))


def _cfg_file() -> Path:
    return _dir() / "alexa.json"


def _token_file() -> Path:
    return _dir() / "credentials" / "alexa_token"


def _load() -> dict:
    try:
        d = json.loads(_cfg_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"devices": dict(d.get("devices") or {}), "routines": dict(d.get("routines") or {})}


def _clean_map(m: dict, what: str) -> dict:
    if len(m) > MAX_DEVICES:
        raise AlexaError(f"No máximo {MAX_DEVICES} {what}.")
    out = {}
    for name, ident in m.items():
        name, ident = " ".join(str(name).split()), str(ident).strip()
        if not _NAME.match(name):
            raise AlexaError("Os nomes podem ter só letras, números e espaço (até 30).")
        if not _ID.match(ident):
            raise AlexaError("O código do dispositivo só pode ter letras, números, - e _ (veja no Voice Monkey).")
        out[name] = ident
    return out


def save(token: Optional[str], devices: dict, routines: dict) -> None:
    """Grava (token None = mantém o atual)."""
    d, r = _clean_map(devices, "dispositivos"), _clean_map(routines, "rotinas")
    if token is not None:
        t = token.strip().strip("\"'")
        if len(t) < 16 or re.search(r"\s", t):
            raise AlexaError("O token parece errado (precisa ter o código inteiro, sem espaços).")
        write_secret(_token_file(), t)
    elif read_secret(_token_file()) is None:
        raise AlexaError("Cole o token do Voice Monkey.")
    _dir().mkdir(parents=True, exist_ok=True)
    _cfg_file().write_text(json.dumps({"devices": d, "routines": r}, ensure_ascii=False, indent=2), encoding="utf-8")


def clear() -> None:
    _cfg_file().unlink(missing_ok=True)
    _token_file().unlink(missing_ok=True)


def status() -> dict:
    """Estado para a tela. Nunca devolve o token."""
    c = _load()
    has = read_secret(_token_file()) is not None
    return {"configured": has and bool(c["devices"] or c["routines"]), "has_token": has, "devices": sorted(c["devices"]), "routines": sorted(c["routines"]),
            "verified": False}


def _pick(mapping: dict, name: str, what: str) -> tuple[str, str]:
    if not mapping:
        raise AlexaError(f"Nenhum {what} cadastrado. Veja em Conexões > Alexa.")
    key = " ".join((name or "").split()).lower()
    if not key:
        if len(mapping) == 1:
            return next(iter(mapping.items()))
        raise AlexaError("Qual? Tenho: " + ", ".join(sorted(mapping)) + ".")
    for n, i in mapping.items():
        if n.lower() == key:
            return n, i
    near = [n for n in mapping if key in n.lower() or n.lower() in key]
    if len(near) == 1:
        return near[0], mapping[near[0]]
    raise AlexaError(f"Não conheço “{name}”. Tenho: " + ", ".join(sorted(mapping)) + ".")


async def _call(path: str, params: dict, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
    token = read_secret(_token_file())
    if not token:
        raise AlexaError("A Alexa ainda não está conectada. Veja em Conexões > Alexa.")
    try:
        async with httpx.AsyncClient(timeout=15, transport=transport, follow_redirects=False) as c:
            r = await c.get(f"{BASE}{path}", params={"token": token, **params})
    except httpx.HTTPError as e:
        logger.info("alexa: sem conexao (%s)", type(e).__name__)
        raise AlexaError("Não consegui falar com o Voice Monkey. Verifique a internet.")
    if r.status_code in (401, 403):
        raise AlexaError("O Voice Monkey recusou o token. Confira em Conexões > Alexa.")
    if r.status_code == 404:
        raise AlexaError("O Voice Monkey não achou esse dispositivo. Confira o código em Conexões > Alexa.")
    if r.status_code >= 400:
        raise AlexaError("O Voice Monkey não aceitou o pedido agora. Tente de novo mais tarde.")


async def say(text: str, device: str = "", *, transport: Optional[httpx.AsyncBaseTransport] = None) -> str:
    t = " ".join((text or "").split())
    if not t:
        raise AlexaError("O que a Alexa deve falar?")
    if len(t) > MAX_TEXT:
        raise AlexaError(f"A mensagem é longa demais para a Alexa (até {MAX_TEXT} letras).")
    if has_secret(t):
        raise AlexaError("Não vou mandar senha, documento ou número de cartão para falar em voz alta.")
    name, ident = _pick(_load()["devices"], device, "dispositivo")
    await _call("/announcement", {"device": ident, "text": t}, transport=transport)
    return f"A Alexa ({name}) falou: “{t}”."


async def routine(name: str, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> str:
    n, ident = _pick(_load()["routines"], name, "rotina")
    await _call("/trigger", {"device": ident}, transport=transport)
    return f"Acionei a rotina “{n}” da Alexa."

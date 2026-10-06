"""Conectar a conta Google (Agenda, Gmail, Drive) com um botao: vai ao site do Google, a pessoa entra e volta.

- credenciais do app (client id/secret) vem do ambiente ou de config/google_oauth.json (cliente "Aplicativo para computador");
- o `state` e o PKCE ficam no servidor, presos a PESSOA que clicou e de uso unico;
- os tokens sao gravados com o provedor que cada skill procura (gmail, google_calendar, google_drive) e protegidos pelo Windows;
- nenhum token volta ao navegador.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlsplit

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
STATE_TTL_S = 600
MAX_PENDING = 30

BASE_SCOPES = ["openid", "email", "profile"]
SERVICES: dict[str, dict] = {
    "calendar": {"label": "Agenda", "provider": "google_calendar", "scope": "https://www.googleapis.com/auth/calendar.events"},
    "email": {"label": "E-mail (Gmail)", "provider": "gmail", "scope": "https://www.googleapis.com/auth/gmail.modify"},
    # ler/buscar os arquivos que ja existem (somente leitura) e guardar os que o Jefrey criar
    "drive": {"label": "Arquivos (Drive)", "provider": "google_drive",
              "scope": "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file"},
    "tasks": {"label": "Tarefas", "provider": "google_tasks", "scope": "https://www.googleapis.com/auth/tasks"},
    "contacts": {"label": "Contatos", "provider": "google_contacts", "scope": "https://www.googleapis.com/auth/contacts.readonly"},
}

_pending: dict[str, dict] = {}


def _config_file() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "google_oauth.json"


def credentials() -> Optional[dict]:
    """{client_id, client_secret} do app Google, ou None se este programa ainda nao foi configurado."""
    cid, sec = os.getenv("JEFREY_OAUTH__CLIENT_ID", ""), os.getenv("JEFREY_OAUTH__CLIENT_SECRET", "")
    if cid and sec:
        return {"client_id": cid, "client_secret": sec}
    try:
        d = json.loads(_config_file().read_text(encoding="utf-8"))
        d = d.get("installed") or d.get("web") or d  # aceita o arquivo baixado do Google Cloud
        if d.get("client_id") and d.get("client_secret"):
            return {"client_id": str(d["client_id"]), "client_secret": str(d["client_secret"])}
    except (OSError, ValueError, AttributeError):
        pass
    return None


def save_credentials(client_id: str, client_secret: str) -> None:
    """Guarda as credenciais do app Google (colar na tela, sem editar arquivos). Valida o formato antes."""
    cid, sec = (client_id or "").strip(), (client_secret or "").strip()
    if not re.fullmatch(r"[0-9]+-[0-9a-z]+\.apps\.googleusercontent\.com", cid):
        raise ValueError("O ID do cliente parece errado. Ele termina com .apps.googleusercontent.com")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{16,100}", sec):
        raise ValueError("A chave secreta parece errada. Copie de novo, sem espaços.")
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"installed": {"client_id": cid, "client_secret": sec}}), encoding="utf-8")


def scopes_for(services: list[str]) -> list[str]:
    bad = [s for s in services if s not in SERVICES]
    if bad or not services:
        raise ValueError("escolha pelo menos um servico valido")
    out = list(BASE_SCOPES)
    for s in dict.fromkeys(services):
        out += [sc for sc in SERVICES[s]["scope"].split() if sc not in out]
    return out


def access_token(user_id: str, service: str) -> str:
    """Token de acesso valido da pessoa para um servico (renova sozinho se venceu). LookupError se ela nao conectou esse servico."""
    import httpx

    from src.jefrey.core.db import get_db
    from src.jefrey.core.secret_store import protect, unprotect

    if service not in SERVICES:
        raise LookupError("servico desconhecido")
    OAuthToken = _table_model()
    with get_db() as s:
        row = s.query(OAuthToken).filter(OAuthToken.user_id == user_id, OAuthToken.provider == SERVICES[service]["provider"]).first()
        if row is None:
            raise LookupError("servico nao conectado")
        access = unprotect(row.access_token)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if row.expires_at is None or row.expires_at > now + timedelta(seconds=60):
            return access
        refresh = unprotect(row.refresh_token) if row.refresh_token else None
        cred = credentials()
        if not refresh or cred is None:
            raise LookupError("precisa entrar de novo")
        r = httpx.post(TOKEN_URL, data={"client_id": cred["client_id"], "client_secret": cred["client_secret"], "refresh_token": refresh,
                                        "grant_type": "refresh_token"}, timeout=15)
        data = r.json() if r.status_code == 200 else {}
        new = data.get("access_token")
        if not new:
            raise LookupError("precisa entrar de novo")
        row.access_token = protect(str(new))
        if data.get("expires_in"):
            row.expires_at = now + timedelta(seconds=int(data["expires_in"]))
        return str(new)


CALLBACK_PATHS = ("/connections/google/callback", "/auth/google/callback")


def registered_redirects() -> list[str]:
    """Enderecos de retorno ja registrados no Google: variavel de ambiente e/ou "redirect_uris" do google_oauth.json (vem no instalador)."""
    out = [r.strip() for r in os.getenv("JEFREY_OAUTH__REDIRECT_URIS", "").split(",") if r.strip()]
    try:
        d = json.loads(_config_file().read_text(encoding="utf-8"))
        d = d.get("installed") or d.get("web") or d
        out += [str(r).strip() for r in (d.get("redirect_uris") or []) if str(r).strip()]
    except (OSError, ValueError, AttributeError):
        pass
    return out


def redirect_uri(origin: str) -> str:
    """Endereco de retorno. Clientes "Web" do Google aceitam so enderecos registrados: se o dono ja registrou um em
    JEFREY_OAUTH__REDIRECT_URIS (na mesma porta do programa), usa ele; senao o padrao (clientes "Computador" aceitam qualquer porta local)."""
    port = urlsplit(origin).port
    for raw in registered_redirects():
        p = urlsplit(raw.strip())
        if p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1") and p.path in CALLBACK_PATHS and p.port == port:
            return raw.strip()
    parts = urlsplit(origin)
    if parts.hostname == "127.0.0.1":  # o endereco que costuma estar cadastrado no Google e o de "localhost" (mesmo computador, mesma porta)
        origin = f"http://localhost:{parts.port}" if parts.port else "http://localhost"
    return origin.rstrip("/") + CALLBACK_PATHS[0]


def diagnose(origin: str) -> dict:
    """Explica em frases simples se o login do Google tende a funcionar e o que cadastrar/fechar se nao."""
    uri = redirect_uri(origin)
    port = urlsplit(origin).port
    if credentials() is None:
        return {"client_type": "unknown", "redirect_uri": uri, "ok": False, "advice": "Falta colar o ID e a chave do Google (veja o quadro acima)."}
    registered = registered_redirects()
    if not registered:  # cliente "Aplicativo para computador": aceita qualquer porta local
        return {"client_type": "desktop", "redirect_uri": uri, "ok": True, "advice": ""}
    if uri in registered:
        return {"client_type": "web", "redirect_uri": uri, "ok": True, "advice": ""}
    why = (f"O Jefrey abriu na porta {port}, mas o Google só conhece a 8000. Feche o outro programa que usa a porta 8000 (por exemplo o Docker) e abra o Jefrey de novo. "
           if port != 8000 else "")
    return {"client_type": "web", "redirect_uri": uri, "ok": False,
            "advice": why + f"Cadastre este endereço no Google Cloud (URIs de redirecionamento): {uri}"}


def has_state(state: str) -> bool:
    e = _pending.get(state or "")
    return bool(e and e["exp"] >= time.time())


def begin(user_id: str, services: list[str], redirect_uri: str, return_to: str = "") -> str:
    """Endereco do Google para a pessoa autorizar. Guarda state/PKCE preso a `user_id`.

    `return_to` e a origem da tela (ex.: http://127.0.0.1:8000): ao voltar do Google a pessoa e levada para la, mesmo que o
    endereco de retorno registrado use outro nome (localhost) e, portanto, outro "armazenamento" do navegador."""
    creds = credentials()
    if creds is None:
        raise LookupError("google nao configurado")
    scopes = scopes_for(services)
    now = time.time()
    state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    _pending[state] = {"verifier": verifier, "user": user_id, "services": list(dict.fromkeys(services)),
                       "redirect": redirect_uri, "return_to": return_to.rstrip("/"), "exp": now + STATE_TTL_S}
    for k in [k for k, v in _pending.items() if v["exp"] < now]:
        _pending.pop(k, None)
    while len(_pending) > MAX_PENDING:
        _pending.pop(next(iter(_pending)))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    q = urlencode({"client_id": creds["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
                   "scope": " ".join(scopes), "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true",
                   "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    return f"{AUTH_URL}?{q}"


def consume_state(state: str) -> Optional[dict]:
    entry = _pending.pop(state or "", None)
    return entry if entry and entry["exp"] >= time.time() else None


def _table_model():
    from src.jefrey.core.models import OAuthToken
    return OAuthToken


def save_tokens(user_id: str, services: list[str], token_data: dict, email: Optional[str]) -> list[str]:
    """Grava (protegido) o token para cada servico escolhido. Devolve os provedores gravados."""
    from src.jefrey.core.db import get_db
    from src.jefrey.core.secret_store import protect

    OAuthToken = _table_model()
    expires = token_data.get("expires_in")
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires))).replace(tzinfo=None) if expires else None
    scopes = str(token_data.get("scope", "")).split()
    saved: list[str] = []
    with get_db() as s:
        for svc in services:
            prov = SERVICES[svc]["provider"]
            s.query(OAuthToken).filter(OAuthToken.user_id == user_id, OAuthToken.provider == prov).delete()
            s.add(OAuthToken(user_id=user_id, provider=prov, access_token=protect(str(token_data["access_token"])),
                             refresh_token=protect(str(token_data["refresh_token"])) if token_data.get("refresh_token") else None,
                             token_type=token_data.get("token_type", "Bearer"), expires_at=expires_at, scopes=scopes, email=email))
            saved.append(prov)
    return saved


def status(user_id: str) -> dict:
    """Estado da conexao da pessoa: nunca devolve tokens."""
    from src.jefrey.core.db import get_db

    OAuthToken = _table_model()
    out = {"configured": credentials() is not None, "connected": False, "email": None, "services": []}
    try:
        with get_db() as s:
            rows = s.query(OAuthToken).filter(OAuthToken.user_id == user_id).all()
            by_provider = {r.provider: r for r in rows}
            for key, meta in SERVICES.items():
                r = by_provider.get(meta["provider"])
                if r is not None:
                    out["services"].append(key)
                    out["email"] = out["email"] or r.email
    except Exception as e:
        logger.warning("google status falhou: %s", type(e).__name__)
    out["connected"] = bool(out["services"])
    return out


def delete_tokens(user_id: str) -> list[str]:
    """Remove os tokens da pessoa; devolve os refresh tokens (ja abertos) para revogar no Google."""
    from src.jefrey.core.db import get_db
    from src.jefrey.core.secret_store import unprotect

    OAuthToken = _table_model()
    providers = [m["provider"] for m in SERVICES.values()]
    revoke: list[str] = []
    with get_db() as s:
        rows = s.query(OAuthToken).filter(OAuthToken.user_id == user_id, OAuthToken.provider.in_(providers)).all()
        for r in rows:
            tok = r.refresh_token or r.access_token
            try:
                revoke.append(unprotect(tok))
            except Exception as _e:
                logger.debug("ignorado (%s): %s", 'google_oauth.py', type(_e).__name__)
            s.delete(r)
    return list(dict.fromkeys(revoke))

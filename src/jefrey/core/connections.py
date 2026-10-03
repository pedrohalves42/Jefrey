"""Conexões de rede — SSRF blocklist e validação de URLs (CIPHER-032)."""

from __future__ import annotations

import logging
import re
from typing import Optional

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# M7 fix: CORS allowlist explícita; A1: deny/false/raise
# Axioma #6: fail-closed por padrão

# Blocked URL patterns for SSRF prevention
# A1: never pass/allow silent — block all internal/private ranges
_BLOCKED_HOSTS = (
    "127.",       # localhost
    "10.",        # private class A
    "172.",       # private class B (172.16-31.x)
    "192.168.",   # private class C
    "169.254.",   # link-local (AWS/GCP metadata endpoint)
    "::1",        # IPv6 localhost
    "localhost",  # hostname localhost
    "postgres",   # internal service name
    "redis",      # internal service name
    "jefrey-",    # Docker compose service names
    "host.docker.internal",  # Docker Desktop host access
)

# Regex for URL validation
_URL_RE = re.compile(r"^https?://")


# Nomes de servico do docker-compose e aliases internos (nao resolvem fora da rede docker,
# mas resolvem DENTRO do container -> precisam ser bloqueados por nome tambem).
_BLOCKED_NAMES = {
    "localhost", "postgres", "redis", "ollama", "mcp-server", "api", "frontend", "brain2",
    "n8n", "grafana", "prometheus", "alertmanager", "host.docker.internal", "gateway.docker.internal",
    "metadata", "metadata.google.internal",
}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")


def _ip_is_internal(ip) -> bool:
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified
            or (getattr(ip, "ipv4_mapped", None) is not None and _ip_is_internal(ip.ipv4_mapped)))


def _is_blocked_url(url: str) -> bool:
    """CIPHER-306: bloqueio SSRF por IP RESOLVIDO (nao por prefixo de texto).

    Antes: comparacao de strings deixava passar 0.0.0.0, IP decimal (2130706433), nomes de
    servico (redis, ollama, mcp-server) e DNS que aponta para 127.0.0.1 (localtest.me), e
    bloqueava IPs publicos como 172.217.x (Google) por engano.
    Fail-closed: erro de parse/resolucao -> bloqueia.
    """
    import ipaddress
    import socket

    try:
        if "::1" in url.lower():
            return True
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return True
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            return True
        if host in _BLOCKED_NAMES or host.startswith("jefrey-") or host.endswith(_BLOCKED_SUFFIXES):
            return True
        if "." not in host and ":" not in host and not host.isdigit():
            return True  # nome curto = rede interna/docker
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                       proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError):
            return True
        if not infos:
            return True
        for info in infos:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
            if _ip_is_internal(ip):
                return True
        return False
    except Exception:
        return True


async def browse(url: str) -> dict:
    """Secure URL browsing with SSRF protection.

    Raises HTTPException if URL is blocked.
    """
    if not _URL_RE.match(url) or _is_blocked_url(url):
        raise HTTPException(
            status_code=400,
            detail="URL bloqueada (SSRF)",
        )
    # ... actual browsing logic
    return {"status": "blocked", "detail": "URL blocked by SSRF protection"}
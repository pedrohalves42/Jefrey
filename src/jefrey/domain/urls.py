"""Enderecos de sites: so os publicos e seguros (sem usuario/senha e sem rede interna)."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit


def clean_public_url(text: str) -> Optional[str]:
    """Endereco seguro para ler ou abrir, ou None. So http(s), com ponto no nome, sem usuario/senha e sem enderecos internos."""
    t = (text or "").strip().strip("\"'")
    if not re.match(r"^https?://", t, re.I):
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", t, re.I):
            t = "https://" + t
        else:
            return None
    p = urlsplit(t)
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname or p.username or p.password or len(t) > 500:
        return None
    if p.hostname in ("localhost",) or re.match(r"^(127\.|10\.|192\.168\.|169\.254\.|0\.)", p.hostname) or p.hostname.endswith((".local", ".internal")):
        return None
    return t


def site_domain(url: str) -> str:
    """Nome do site sem o www ("https://www.g1.com/x" -> "g1.com")."""
    return re.sub(r"^www\.", "", (urlsplit(url).hostname or "").lower())

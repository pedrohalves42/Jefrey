"""Redes sociais (REGRAS PURAS): quais redes o Jefrey abre, contagem de novidades pelo titulo da pagina e como validar um carrossel/post escrito pelo modelo.

O Jefrey NAO posta sozinho: ele escreve e gera as imagens; quem publica e a pessoa (as redes bloqueiam contas que usam robos).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from src.jefrey.domain.learning import has_secret

NETWORKS: dict[str, tuple[str, str]] = {  # id -> (nome, endereco fixo: a janela so abre estes)
    "whatsapp": ("WhatsApp", "https://web.whatsapp.com"),
    "instagram": ("Instagram", "https://www.instagram.com"),
    "facebook": ("Facebook", "https://www.facebook.com"),
    "x": ("X (Twitter)", "https://x.com"),
    "telegram": ("Telegram", "https://web.telegram.org/k/"),
}
POST_LIMITS = {"instagram": 2200, "facebook": 3000, "x": 280, "telegram": 4000, "whatsapp": 600}

MIN_SLIDES, MAX_SLIDES = 3, 10
TITLE_MAX, BODY_MAX, CAPTION_MAX, MAX_TAGS = 60, 220, 600, 8


def network_name(net_id: str) -> Optional[str]:
    return NETWORKS.get(net_id, (None, ""))[0]


def unread_from_title(title: str) -> int:
    """'(3) Facebook' ou '(12) Home / X' -> 3, 12. Sem numero no inicio = 0."""
    m = re.match(r"^\s*\((\d{1,4})\+?\)", title or "")
    return int(m.group(1)) if m else 0


def slug(text: str, limit: int = 40) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(c) != "Mn")
    return (re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:limit]) or "post"


@dataclass(frozen=True)
class Slide:
    title: str
    body: str = ""


@dataclass(frozen=True)
class Carousel:
    title: str
    slides: tuple[Slide, ...]
    caption: str = ""
    hashtags: tuple[str, ...] = field(default_factory=tuple)


CAROUSEL_SYSTEM = (
    "Voce cria carrosseis para redes sociais em portugues do Brasil, claros e diretos. Responda SOMENTE um JSON: "
    '{{"title": "...", "slides": [{{"title": "...", "body": "..."}}], "caption": "...", "hashtags": ["#..."]}}. '
    "O primeiro slide e a capa (so titulo chamativo); o ultimo e um convite a acao. Use {n} slides. Titulos com ate {tmax} caracteres e textos "
    "com ate {bmax}. Nunca invente numeros, precos, promessas ou dados pessoais; se nao tiver certeza, nao afirme."
)
POST_SYSTEM = (
    "Voce escreve posts para {net} em portugues do Brasil, no tom da pessoa. Responda SOMENTE o texto do post, sem aspas, com no maximo {limit} "
    "caracteres. Nunca invente fatos, numeros ou dados pessoais."
)


def _json(raw: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _clean(v, limit: int) -> str:
    return " ".join(str(v or "").split())[:limit]


def parse_carousel(raw: str, topic: str = "") -> Optional[Carousel]:
    """Valida a resposta do modelo. None se nao presta (sem slides suficientes, com dado sensivel...)."""
    d = _json(raw)
    if not d:
        return None
    slides: list[Slide] = []
    for s in d.get("slides") or []:
        if isinstance(s, dict):
            title, body = _clean(s.get("title"), TITLE_MAX), _clean(s.get("body"), BODY_MAX)
            if title and not has_secret(title + " " + body):
                slides.append(Slide(title, body))
    slides = slides[:MAX_SLIDES]
    if len(slides) < MIN_SLIDES:
        return None
    caption = _clean(d.get("caption"), CAPTION_MAX)
    if has_secret(caption):
        return None
    tags = []
    for t in d.get("hashtags") or []:
        tag = "#" + re.sub(r"[^0-9A-Za-zÀ-ÿ_]", "", str(t))
        if len(tag) > 1 and tag not in tags:
            tags.append(tag[:30])
    title = _clean(d.get("title"), TITLE_MAX) or _clean(topic, TITLE_MAX) or slides[0].title
    return Carousel(title, tuple(slides), caption, tuple(tags[:MAX_TAGS]))


def clean_post(raw: str, net_id: str) -> Optional[str]:
    """Texto final do post, cortado no limite da rede. None se vazio ou com dado sensivel."""
    t = (raw or "").strip().strip("\"'“”")
    limit = POST_LIMITS.get(net_id, 1000)
    if not t or has_secret(t):
        return None
    return t[:limit].rstrip()


# ---------------- publicar (com travas para nao parecer robo) ----------------
PUBLISH_NETWORKS = ("x", "facebook", "instagram")
MAX_IMAGES = {"x": 4, "facebook": 10, "instagram": 10}
MAX_PER_DAY = 5
MIN_GAP_S = 600  # 10 minutos entre duas publicacoes na mesma rede


def validate_publish(net: str, text: str, n_images: int) -> Optional[str]:
    """Texto de erro para a pessoa, ou None se pode publicar."""
    if net not in PUBLISH_NETWORKS:
        return "Posso publicar no X, no Facebook e no Instagram. Para as outras redes, copie o texto e publique você."
    t = (text or "").strip()
    if net != "instagram" and not t and n_images == 0:
        return "Falta o texto do post."
    if has_secret(t):
        return "O texto parece ter senha ou número de documento. Não publico isso."
    if len(t) > POST_LIMITS.get(net, 1000):
        return f"O texto passa do limite de {POST_LIMITS[net]} caracteres do {network_name(net)}."
    if net == "instagram" and n_images == 0:
        return "O Instagram precisa de imagens: crie um carrossel e publique a pasta dele."
    if n_images > MAX_IMAGES[net]:
        return f"O {network_name(net)} aceita no máximo {MAX_IMAGES[net]} imagens por publicação."
    return None


def publish_gap(history: list[float], now: float) -> Optional[str]:
    """`history`: instantes (segundos) das ultimas publicacoes desta rede. Texto de espera, ou None se pode publicar agora."""
    today = [h for h in history if now - h < 86400]
    if len(today) >= MAX_PER_DAY:
        return f"Já publiquei {MAX_PER_DAY} vezes nas últimas 24 horas. Espere um pouco para não parecer robô e perder a conta."
    if today and now - max(today) < MIN_GAP_S:
        faltam = int((MIN_GAP_S - (now - max(today))) // 60) + 1
        return f"Publiquei há pouco. Espere mais {faltam} min para não parecer robô."
    return None

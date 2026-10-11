"""Painel "Hoje": agenda, lembretes, clima, noticias, mercado e a sua regiao, num lugar so.

Regras:
- fontes publicas e gratuitas, SEM chave e sem mandar nada seu: so o nome da cidade vai ao servico de clima;
- cada cartao falha sozinho (um fora do ar nunca derruba o painel) e tem estado: ok | parcial | erro | falta_regiao;
- titulos de noticias sao DADO de terceiros: viram so texto na tela, nunca vao ao modelo nem acionam ferramentas;
- links so https; feeds com DOCTYPE/ENTITY ou enormes sao descartados;
- resposta em cache por 15 minutos.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional
from urllib.parse import urlsplit

TTL = 15 * 60
MAX_FEED = 2_000_000  # o feed real do g1 tem ~420 KB
UFS = {"ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"}
G1 = "https://g1.globo.com/rss/g1/"
FEEDS = {"news": G1, "economy": G1 + "economia/"}
# Assuntos que a pessoa pode escolher: "Para voce" mostra so o que ela marcou (nada de manchete aleatoria).
INTERESTS = {
    "tecnologia": ("Tecnologia", G1 + "tecnologia/"),
    "ciencia": ("Ciência e saúde", G1 + "ciencia-e-saude/"),
    "politica": ("Política", G1 + "politica/"),
    "mundo": ("Mundo", G1 + "mundo/"),
    "economia": ("Dinheiro e economia", G1 + "economia/"),
    "esportes": ("Esportes", "https://ge.globo.com/rss/ge/"),
    "cultura": ("Cultura e famosos", G1 + "pop-arte/"),
    "carros": ("Carros", G1 + "carros/"),
    "educacao": ("Educação", G1 + "educacao/"),
    "natureza": ("Natureza", G1 + "natureza/"),
    "viagem": ("Turismo e viagem", G1 + "turismo-e-viagem/"),
}
MAX_INTERESTS = 6
_TAG = re.compile(r"<[^>]+>")
_WEATHER_CODES = {0: "céu limpo", 1: "poucas nuvens", 2: "parcialmente nublado", 3: "nublado", 45: "neblina", 48: "neblina", 51: "garoa", 53: "garoa", 55: "garoa forte",
                  61: "chuva fraca", 63: "chuva", 65: "chuva forte", 71: "neve", 80: "pancadas de chuva", 81: "pancadas de chuva", 82: "chuva muito forte", 95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas com granizo"}



def normalize_prefs(d: Any) -> dict:
    """Preferencias lidas do arquivo -> {city, uf, interests} sempre validas."""
    raw = d.get("interests", [])
    picked = [i for i in raw if isinstance(i, str) and i in INTERESTS][:MAX_INTERESTS] if isinstance(raw, list) else []
    return {"city": str(d.get("city", ""))[:60], "uf": str(d.get("uf", "")).lower() if str(d.get("uf", "")).lower() in UFS else "", "interests": picked}


def validate_region(city: str, uf: str) -> tuple[str, str]:
    city, uf = " ".join((city or "").split()), (uf or "").strip().lower()
    if uf not in UFS:
        raise ValueError("Escolha o seu estado.")
    if not re.fullmatch(r"[A-Za-zÀ-ÿ' .-]{2,60}", city):
        raise ValueError("Escreva o nome da sua cidade (só letras, até 60).")
    return city, uf


def clean_interests(ids) -> list[str]:
    """So os assuntos conhecidos, sem repetir, no maximo MAX_INTERESTS."""
    clean: list[str] = []
    for i in ids or []:
        if isinstance(i, str) and i in INTERESTS and i not in clean:
            clean.append(i)
    return clean[:MAX_INTERESTS]


def weather_summary(res: dict, d: dict) -> dict:
    """Resposta da previsao (Open-Meteo) -> cartao do painel."""
    cur, day = d.get("current") or {}, d.get("daily") or {}
    first = lambda k: (day.get(k) or [None])[0]
    desc = _WEATHER_CODES.get(int(cur.get("weather_code", 0) or 0), "tempo variável")
    rain = first("precipitation_probability_max")
    summary = f"Agora {round(cur.get('temperature_2m', 0))} °C, {desc}. Hoje entre {round(first('temperature_2m_min'))} e {round(first('temperature_2m_max'))} °C"
    summary += f", chance de chuva de {rain}%." if rain is not None else "."
    return {"place": ", ".join(x for x in (res.get("name"), res.get("admin1")) if x), "temp": cur.get("temperature_2m"), "max": first("temperature_2m_max"),
            "min": first("temperature_2m_min"), "rain_pct": rain, "summary": summary}


def mix_interest_news(per_topic: dict[str, list[dict]], limit: int = 9) -> list[dict]:
    """Intercala os assuntos (um de cada, em rodizio) para nenhum dominar, sem repetir link."""
    out: list[dict] = []
    seen: set[str] = set()
    pools = {k: list(v) for k, v in per_topic.items()}
    while len(out) < limit and any(pools.values()):
        for k in list(pools):
            while pools[k]:
                n = pools[k].pop(0)
                if n["link"] not in seen:
                    seen.add(n["link"])
                    out.append({**n, "topic": INTERESTS[k][0]})
                    break
            if len(out) >= limit:
                break
    return out


def _clean(s: str, n: int = 180) -> str:
    return " ".join(html.unescape(_TAG.sub("", s or "")).split())[:n]


def parse_rss(content: bytes, limit: int = 6) -> list[dict]:
    """Titulos e links (https) de um RSS. Qualquer coisa estranha vira lista vazia."""
    if not content or len(content) > MAX_FEED or b"<!DOCTYPE" in content[:2000].upper() or b"<!ENTITY" in content.upper():
        return []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        p = urlsplit(link)
        if title and p.scheme == "https" and p.hostname and not p.username:
            out.append({"title": title, "link": link})
        if len(out) >= limit:
            break
    return out



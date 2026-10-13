"""Casos de uso das redes sociais: escrever carrosseis (com as imagens prontas) e posts. Nada e publicado aqui: quem posta e a pessoa."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.jefrey.domain.social import (
    CAROUSEL_SYSTEM, MAX_SLIDES, MIN_SLIDES, NETWORKS, POST_LIMITS, POST_SYSTEM, BODY_MAX, TITLE_MAX, clean_post, parse_carousel, slug,
)
from src.jefrey.ports.registry import use

logger = logging.getLogger(__name__)

NO_MODEL = "Não consegui escrever agora (sem conexão com a inteligência). Tente de novo daqui a pouco."


def _about(env: Any, user_id: str) -> str:
    try:
        name = env.person_name(user_id)
        known = env.profile_lines(user_id)
    except Exception:
        return ""
    bits = ([f"A pessoa se chama {name}."] if name else []) + (["O que voce sabe dela: " + "; ".join(known[:6])] if known else [])
    return ("\n" + " ".join(bits)) if bits else ""


async def make_carousel(user_id: str, topic: str, slides: int = 6, theme: str = "escuro") -> dict:
    """Escreve o carrossel sobre `topic` e desenha as imagens. Devolve {ok, message, title, folder, files, caption, hashtags}."""
    topic = " ".join((topic or "").split())[:300]
    if len(topic) < 3:
        return {"ok": False, "message": "Sobre o que é o carrossel?"}
    n = max(MIN_SLIDES, min(MAX_SLIDES, int(slides or 6)))
    env = use("social_env")
    system = CAROUSEL_SYSTEM.format(n=n, tmax=TITLE_MAX, bmax=BODY_MAX) + _about(env, user_id)
    try:
        raw = await env.llm_text([{"role": "system", "content": system}, {"role": "user", "content": f"<assunto>\n{topic}\n</assunto>"}])
    except Exception as e:
        logger.info("carrossel: modelo indisponivel (%s)", type(e).__name__)
        return {"ok": False, "message": NO_MODEL}
    car = parse_carousel(raw, topic)
    if car is None:
        return {"ok": False, "message": "Não consegui montar um carrossel bom desta vez. Tente de novo ou mude o assunto."}
    folder = env.output_dir(f"{slug(car.title)}-{datetime.now():%Y%m%d-%H%M}")
    files = env.render(car, folder, theme)
    return {"ok": True, "message": f"Pronto: {len(files)} imagens em {folder}", "title": car.title, "folder": str(folder),
            "files": [str(f) for f in files], "caption": car.caption, "hashtags": list(car.hashtags),
            "slides": [{"title": s.title, "body": s.body} for s in car.slides]}


async def make_post(user_id: str, network: str, topic: str) -> dict:
    """Escreve um post para a rede (so o texto)."""
    net = (network or "").strip().lower().replace("twitter", "x")
    if net not in NETWORKS:
        return {"ok": False, "message": "Escolha uma rede: " + ", ".join(NETWORKS) + "."}
    topic = " ".join((topic or "").split())[:400]
    if len(topic) < 3:
        return {"ok": False, "message": "Sobre o que é o post?"}
    env = use("social_env")
    system = POST_SYSTEM.format(net=NETWORKS[net][0], limit=POST_LIMITS[net]) + _about(env, user_id)
    try:
        raw = await env.llm_text([{"role": "system", "content": system}, {"role": "user", "content": f"<assunto>\n{topic}\n</assunto>"}])
    except Exception as e:
        logger.info("post: modelo indisponivel (%s)", type(e).__name__)
        return {"ok": False, "message": NO_MODEL}
    text = clean_post(raw, net)
    if not text:
        return {"ok": False, "message": "Não consegui escrever um post bom desta vez. Tente de novo."}
    return {"ok": True, "network": net, "text": text, "message": text}


async def publish(user_id: str, network: str, text: str, folder: str = "", send: bool = True) -> dict:
    """Publica na rede pela janela do Jefrey (a pessoa ja entrou na conta). Trava de ritmo e limites antes. {ok, message}."""
    import time

    from src.jefrey.domain.social import publish_gap, validate_publish

    net = (network or "").strip().lower().replace("twitter", "x")
    env = use("social_env")
    try:
        images = env.read_images(folder) if folder else []
    except Exception as e:
        logger.info("publicar: pasta das imagens invalida (%s)", type(e).__name__)
        return {"ok": False, "message": "Não achei as imagens desse carrossel."}
    problem = validate_publish(net, text, len(images))
    if problem:
        return {"ok": False, "message": problem}
    wait = publish_gap(env.publish_history(net), time.time())
    if wait and send:
        return {"ok": False, "message": wait}
    result = await env.publish(net, text.strip(), images, send)
    if result.get("ok") and send:
        env.record_publish(net)
    return {"ok": bool(result.get("ok")), "message": str(result.get("message") or "Não consegui publicar agora.")}

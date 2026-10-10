"""Caso de uso: o Jefrey olha a tela da pessoa (so quando ela pede e aprova) e explica em linguagem simples. A imagem nao e guardada."""
from __future__ import annotations

import asyncio
import logging

from src.jefrey.domain.vision import SYSTEM, clean_answer, question_or_default
from src.jefrey.ports.registry import use

logger = logging.getLogger(__name__)


async def look(user_id: str, question: str = "") -> dict:
    env = use("vision_env")
    try:
        b64 = await asyncio.to_thread(env.capture_b64)
    except Exception as e:
        logger.info("ver a tela: captura falhou (%s)", type(e).__name__)
        return {"ok": False, "message": "Não consegui tirar a foto da tela agora."}
    try:
        raw = await env.describe(question_or_default(question), SYSTEM, b64)
    except Exception as e:
        logger.info("ver a tela: modelo nao respondeu (%s)", type(e).__name__)
        return {"ok": False, "message": "Não consegui entender a imagem agora. Um dos meus cérebros precisa saber ver imagens (por exemplo o Gemini). Veja em Conexões → Cérebros."}
    text = clean_answer(raw)
    return {"ok": bool(text), "message": text or "Não consegui entender o que aparece na tela."}

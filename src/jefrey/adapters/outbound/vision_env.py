"""O que "ver a tela" usa do mundo de fora: tirar a foto da tela (com a janela do Jefrey fora do caminho) e perguntar ao modelo."""
from __future__ import annotations

import binascii
import io
from typing import Any

MAX_SIDE = 1280


def to_jpeg_b64(img: Any, max_side: int = MAX_SIDE, quality: int = 72) -> str:
    """Reduz a imagem (a tela pode ter 4K) e devolve JPEG em base64 padrao (formato que os provedores pedem)."""
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return binascii.b2a_base64(buf.getvalue(), newline=False).decode("ascii")  # base64 padrao (o que os provedores pedem)


class VisionEnvironment:
    def capture_b64(self) -> str:
        from src.jefrey.native import control

        img = control.grab_screen()  # a janela do Jefrey sai do caminho e volta depois
        if img is None:
            from PIL import ImageGrab

            img = ImageGrab.grab()
        return to_jpeg_b64(img)

    async def describe(self, prompt: str, system: str, jpeg_b64: str) -> str:
        from src.jefrey.core.llm_provider import get_llm_client

        return await get_llm_client().describe_image(prompt, system, jpeg_b64)


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("vision_env", VisionEnvironment)

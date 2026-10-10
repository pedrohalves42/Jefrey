"""O que os casos de uso das redes sociais usam do mundo de fora: o modelo, o perfil, as pastas e o desenho das imagens."""
from __future__ import annotations

from src.jefrey.domain.llm_roles import chat_as

from pathlib import Path
from typing import Any, Optional


class SocialEnvironment:
    async def llm_text(self, messages: list[dict]) -> str:
        from src.jefrey.core.llm_provider import get_llm_client

        return await chat_as(get_llm_client(), messages, "escrita")

    def person_name(self, user_id: str) -> Optional[str]:
        from src.jefrey.core.profile import ProfileStore

        return ProfileStore().get_name(user_id)

    def profile_lines(self, user_id: str) -> list:
        from src.jefrey.core.learning import FactStore

        return FactStore().profile_lines(user_id, 6)

    def output_dir(self, name: str) -> Path:
        from src.jefrey.adapters.outbound.carousel_renderer import default_output_root

        return default_output_root() / name

    def render(self, carousel: Any, folder: Path, theme: str) -> list[Path]:
        from src.jefrey.adapters.outbound.carousel_renderer import render_carousel

        return render_carousel(carousel, folder, theme)


    # ---- publicar ----
    def read_images(self, folder: str) -> list:
        """Imagens (slide-*.png) de uma pasta de carrossel, como [{name, type, b64}]. So pastas dentro da pasta dos carrosseis."""
        import base64

        from src.jefrey.adapters.outbound.carousel_renderer import default_output_root

        root, target = default_output_root().resolve(), Path(folder).resolve()
        if root not in target.parents or not target.is_dir():
            raise ValueError("pasta fora da pasta dos carrosseis")
        return [{"name": f.name, "type": "image/png", "b64": base64.b64encode(f.read_bytes()).decode()} for f in sorted(target.glob("slide-*.png"))[:10]]

    def _log_file(self) -> Path:
        import os

        return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "publicacoes.json"

    def publish_history(self, net: str) -> list:
        import json

        try:
            d = json.loads(self._log_file().read_text(encoding="utf-8"))
            return [float(x) for x in d.get(net, [])]
        except (OSError, ValueError, AttributeError):
            return []

    def record_publish(self, net: str) -> None:
        import json
        import time

        f = self._log_file()
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        now = time.time()
        d[net] = [x for x in d.get(net, []) if now - float(x) < 86400 * 2] + [now]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d), encoding="utf-8")

    async def publish(self, net: str, text: str, images: list, send: bool) -> dict:
        import asyncio

        from src.jefrey.native import control

        return await asyncio.to_thread(control.publish_in_site, net, text, images, send)


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("social_env", SocialEnvironment)

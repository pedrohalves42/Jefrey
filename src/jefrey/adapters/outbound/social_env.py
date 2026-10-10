"""O que os casos de uso das redes sociais usam do mundo de fora: o modelo, o perfil, as pastas e o desenho das imagens."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


class SocialEnvironment:
    async def llm_text(self, messages: list[dict]) -> str:
        from src.jefrey.core.llm_provider import get_llm_client

        return await get_llm_client().chat(messages)

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


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("social_env", SocialEnvironment)

"""Desenha as imagens do carrossel (PNG 1080x1350, o formato vertical do Instagram) com a Pillow. Sem internet, sem custo.

Capa (titulo grande), slides (titulo + texto) e o ultimo com o convite. Salva tambem a legenda em legenda.txt.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.jefrey.domain.social import Carousel

logger = logging.getLogger(__name__)

SIZE = (1080, 1350)
MARGIN = 96
THEMES = {  # (fundo de cima, fundo de baixo, texto, destaque)
    "escuro": ((9, 18, 32), (22, 38, 68), (240, 247, 255), (86, 204, 242)),
    "claro": ((250, 250, 247), (226, 236, 245), (24, 36, 54), (0, 122, 204)),
    "verde": ((8, 38, 30), (16, 84, 66), (236, 252, 245), (110, 231, 183)),
    "quente": ((52, 20, 12), (140, 52, 24), (255, 244, 235), (253, 186, 116)),
}
FONT_DIRS = (Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"), Path("/Library/Fonts"))


def _font(bold: bool, size: int):
    from PIL import ImageFont

    names = (["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    for d in FONT_DIRS:
        for n in names:
            f = d / n
            if f.is_file():
                try:
                    return ImageFont.truetype(str(f), size)
                except OSError:
                    continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in (text or "").split("\n"):
        cur = ""
        for word in para.split():
            test = f"{cur} {word}".strip()
            if draw.textlength(test, font=font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _background(theme: tuple):
    from PIL import Image, ImageDraw

    top, bottom = theme[0], theme[1]
    img = Image.new("RGB", SIZE, top)
    d = ImageDraw.Draw(img)
    for y in range(SIZE[1]):
        t = y / (SIZE[1] - 1)
        d.line([(0, y), (SIZE[0], y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def _fit(draw, text: str, bold: bool, start: int, floor: int, max_w: int, max_lines: int):
    """A maior fonte (entre start e floor) em que o texto cabe em max_lines linhas."""
    for size in range(start, floor - 1, -4):
        f = _font(bold, size)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
    f = _font(bold, floor)
    return f, _wrap(draw, text, f, max_w)[:max_lines], floor


def render_slide(c: Carousel, index: int, theme_name: str = "escuro"):
    from PIL import ImageDraw

    theme = THEMES.get(theme_name, THEMES["escuro"])
    _, _, fg, accent = theme
    img = _background(theme)
    d = ImageDraw.Draw(img)
    s = c.slides[index]
    n = len(c.slides)
    max_w = SIZE[0] - 2 * MARGIN
    d.rectangle([MARGIN, 120, MARGIN + 120, 132], fill=accent)  # detalhe de cor
    if index == 0:  # capa
        f, lines, size = _fit(d, s.title, True, 104, 60, max_w, 7)
        h = len(lines) * int(size * 1.2)
        y = (SIZE[1] - h) // 2
        for ln in lines:
            d.text((MARGIN, y), ln, font=f, fill=fg)
            y += int(size * 1.2)
        d.text((MARGIN, SIZE[1] - 190), "Arraste para o lado  →", font=_font(False, 40), fill=accent)
    else:
        f, lines, size = _fit(d, s.title, True, 80, 48, max_w, 4)
        title_h = len(lines) * int(size * 1.25)
        blines: list[str] = []
        fb, bsize, body_h = None, 0, 0
        if s.body:
            fb, blines, bsize = _fit(d, s.body, False, 62, 38, max_w, 12)
            body_h = 48 + len(blines) * int(bsize * 1.4)
        y = max(200, (SIZE[1] - (title_h + body_h)) // 2 - 40)  # o bloco fica no meio da imagem
        for ln in lines:
            d.text((MARGIN, y), ln, font=f, fill=accent)
            y += int(size * 1.25)
        if blines:
            y += 48
            for ln in blines:
                d.text((MARGIN, y), ln, font=fb, fill=fg)
                y += int(bsize * 1.4)
    d.text((MARGIN, SIZE[1] - 110), f"{index + 1}/{n}", font=_font(False, 36), fill=accent)
    return img


def render_carousel(c: Carousel, out_dir: Path, theme_name: str = "escuro") -> list[Path]:
    """Grava slide-01.png ... e legenda.txt em `out_dir`. Devolve os caminhos das imagens."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for i in range(len(c.slides)):
        p = out_dir / f"slide-{i + 1:02d}.png"
        render_slide(c, i, theme_name).save(p, "PNG", optimize=True)
        files.append(p)
    legenda = (c.caption + "\n\n" + " ".join(c.hashtags)).strip()
    (out_dir / "legenda.txt").write_text(legenda + "\n", encoding="utf-8")
    return files


def open_folder(path: Path) -> bool:
    import os
    import sys

    if sys.platform != "win32" or not path.is_dir():
        return False
    os.startfile(str(path))  # type: ignore[attr-defined]
    return True


def default_output_root() -> Path:
    import os

    env: Optional[str] = os.getenv("JEFREY_SOCIAL_DIR")
    return Path(env) if env else Path.home() / "Documents" / "Jefrey" / "carrosseis"

"""Redes sociais: criar carrossel/post (o Jefrey escreve; a pessoa publica), lista das redes e abrir a pasta dos carrosseis."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.application.social import make_carousel, make_post
from src.jefrey.domain.social import NETWORKS

router = APIRouter(prefix="/social", tags=["social"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class CarouselBody(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    slides: int = Field(default=6, ge=3, le=10)
    theme: str = Field(default="escuro", pattern="^(escuro|claro|verde|quente)$")


class PostBody(BaseModel):
    network: str = Field(max_length=20)
    topic: str = Field(min_length=3, max_length=400)


class FolderBody(BaseModel):
    path: str = Field(max_length=500)


@router.get("/networks")
async def networks(request: Request):
    """As redes que o Jefrey sabe abrir e quantas novidades cada janela mostra (so das janelas ja abertas)."""
    _user(request)
    from src.jefrey.native import control

    counts = control.site_counts()
    return {"networks": [{"id": k, "name": v[0], "unread": counts.get(k, 0)} for k, v in NETWORKS.items()], "window": control.has_window()}


@router.post("/carousel")
async def carousel(body: CarouselBody, request: Request):
    r = await make_carousel(_user(request), body.topic, body.slides, body.theme)
    if not r["ok"]:
        raise HTTPException(status_code=503 if "agora" in r["message"] else 422, detail=r["message"])
    return r


@router.post("/post")
async def post(body: PostBody, request: Request):
    r = await make_post(_user(request), body.network, body.topic)
    if not r["ok"]:
        raise HTTPException(status_code=422, detail=r["message"])
    return r


@router.post("/open-folder")
async def open_folder(body: FolderBody, request: Request):
    """Abre a pasta de um carrossel no Windows. So pastas dentro da pasta dos carrosseis."""
    _user(request)
    from pathlib import Path

    from src.jefrey.adapters.outbound.carousel_renderer import default_output_root, open_folder as _open

    root = default_output_root().resolve()
    target = Path(body.path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=400, detail="Essa pasta não é de um carrossel.")
    if not _open(target):
        raise HTTPException(status_code=404, detail="Não consegui abrir a pasta.")
    return {"ok": True}

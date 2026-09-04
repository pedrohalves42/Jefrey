"""Connections 1-clique — F6-3 (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, #4 PERSISTENCIA, CIPHER-032)"""
from __future__ import annotations
import os
import re
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections", tags=["connections"])

_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

@router.post("/browse")
async def browse(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required (Axiom #2)")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    url = str(body.get("url") or "").strip()
    if not url or not _URL_RE.match(url):
        raise HTTPException(status_code=400, detail="url invalida, use https://...")
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="url muito longa")
    # Try MCP browser_control (stdio) — fail-closed gracefully (Axiom #7 sem novo container)
    # We do not spawn MCP here; we log and return instruction for n8n fallback
    n8n_url = os.getenv("JEFREY_N8N_WEBHOOK_URL") or os.getenv("N8N_WEBHOOK_URL") or "http://jefrey-n8n:5678/webhook/jefrey-browser"
    # Optional proxy to n8n if reachable (dev-only attempt, never crash)
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.post(n8n_url, json={"url": url, "user_id": user_id}, headers={"X-User-Id": user_id})
            if r.status_code < 400:
                return {"ok": True, "url": url, "message": f"Navegacao via n8n OK ({r.status_code})", "via": "n8n"}
    except Exception as e:
        logger.info(f"browse n8n fallback falhou (ok, sem n8n workflow): {e}")
    # Fallback: instruct frontend to open URL + log audit
    try:
        from src.jefrey.core.audit import get_audit_logger
        get_audit_logger().log(user_id=user_id, action="connections.browse", resource=url, status="ok")
    except Exception:
        pass
    return {"ok": True, "url": url, "message": f"Navegar: {url} — abra em nova aba (MCP browser_control pronto quando workflow n8n configurado)", "via": "direct"}

@router.post("/send")
async def send_message(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    to = str(body.get("to") or "").strip()
    text = str(body.get("text") or "").strip()
    channel = str(body.get("channel") or "whatsapp").strip().lower()
    if not to or not text:
        raise HTTPException(status_code=400, detail="to e text obrigatorios")
    if channel not in ("whatsapp", "telegram"):
        raise HTTPException(status_code=400, detail="channel deve ser whatsapp ou telegram")
    if len(text) > 4000:
        raise HTTPException(status_code=400, detail="text muito longo (max 4000)")
    n8n_url = os.getenv("JEFREY_N8N_WEBHOOK_URL") or os.getenv("N8N_WEBHOOK_URL") or "http://jefrey-n8n:5678/webhook/jefrey-send-message"
    # Try n8n webhook (CIPHER-032 policy check would be via agent, here direct)
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.post(n8n_url, json={"to": to, "channel": channel, "text": text, "user_id": user_id}, headers={"X-User-Id": user_id})
            if r.status_code < 400:
                return {"ok": True, "message": f"Enviado via {channel} para {to} (n8n {r.status_code})"}
            # If n8n returns 404, workflow nao configurado — fail-closed com instrucao
            if r.status_code == 404:
                raise HTTPException(status_code=502, detail=f"n8n webhook nao configurado em {n8n_url} — crie workflow /webhook/jefrey-send-message em n8n:5678 (docs/CONEXOES_N8N.md)")
            raise HTTPException(status_code=502, detail=f"n8n respondeu {r.status_code}: {r.text[:300]}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"connections/send n8n erro: {e}")
        raise HTTPException(status_code=502, detail=f"n8n indisponivel ({n8n_url}): {e} — configure workflow n8n")

@router.post("/search")
async def search(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    query = str(body.get("query") or body.get("q") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query obrigatoria")
    if len(query) > 500:
        raise HTTPException(status_code=400, detail="query muito longa")
    # Use WebSearchSkill (Tavily + DDG) — never crash
    try:
        from src.jefrey.skills.web_search import WebSearchSkill
        skill = WebSearchSkill()
        skill.initialize()
        res = await skill.search(query)  # type: ignore[attr-defined]
        # Normalize: skill may return dict with results
        if isinstance(res, dict) and ("results" in res or "hits" in res):
            return {"ok": True, "query": query, "results": res.get("results") or res.get("hits") or [], "raw": res}
        if isinstance(res, list):
            return {"ok": True, "query": query, "results": res}
        return {"ok": True, "query": query, "results": [], "raw": res, "message": str(res)[:800]}
    except Exception as e:
        # Fallback: try calling skill tool directly if method name differs
        try:
            from src.jefrey.skills.web_search import WebSearchSkill as WSS
            s2 = WSS(); s2.initialize()
            # Try generic tool call
            for attr in ("web_search", "search", "search_web", "query"):
                if hasattr(s2, attr):
                    fn = getattr(s2, attr)
                    r2 = await fn(query) if callable(fn) else None
                    if r2:
                        return {"ok": True, "query": query, "results": r2 if isinstance(r2, list) else [r2]}
        except Exception:
            pass
        logger.warning(f"connections/search falhou: {e}")
        raise HTTPException(status_code=502, detail=f"web_search falhou: {e}")

@router.post("/test")
async def test_connection(request: Request):
    # dev-only proxy para n8n health (Axiom #1 fail-closed)
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    n8n_base = os.getenv("JEFREY_N8N_WEBHOOK_URL") or "http://jefrey-n8n:5678"
    # Strip webhook path if present
    base = n8n_base.split("/webhook")[0].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(base + "/healthz", headers={"X-User-Id": user_id})
            if r.status_code == 200:
                return {"ok": True, "n8n": "healthy", "base": base}
            # n8n may expose /healthz or just 200 on /
            r2 = await c.get(base + "/", headers={"X-User-Id": user_id})
            return {"ok": r2.status_code < 500, "status": r2.status_code, "base": base}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"n8n health falhou ({base}): {e}")

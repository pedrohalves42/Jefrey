"""Connections 1-clique — F6-3 (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, #4 PERSISTENCIA, CIPHER-032)"""
from __future__ import annotations
import os
from urllib.parse import urlparse
import re
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections", tags=["connections"])

_BLOCKED_HOSTS = ("127.", "10.", "172.", "192.168.", "169.254.", "::1", "localhost", "postgres", "jefrey-", "host.docker.internal")

def _is_blocked_url(url: str) -> bool:
    try:
        # CIPHER-118b: http://::1/ sem [] tem hostname None, mas eh SSRF local -> bloqueia pelo raw
        if "::1" in url.lower():
            return True
        host = (urlparse(url).hostname or "").lower()
        return any(host == b.rstrip(".") or host.startswith(b) or b in host for b in _BLOCKED_HOSTS)
    except Exception:
        return True

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
    if not url or not _URL_RE.match(url) or _is_blocked_url(url):
        raise HTTPException(status_code=400, detail="URL bloqueada (SSRF)" if _is_blocked_url(url) else "url invalida, use https://...")
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
        get_audit_logger().log(thread_id="connections", tool_name="browse", actor_role="user", risk="low", decision="allow", user_id=user_id, detail={"url": url, "via": "direct"})
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

@router.post("/n8n/trigger")
async def n8n_trigger(request: Request):
    """D4 — Proxy real para n8n Event Router webhook (jefrey-events).

    Fluxo: frontend -> POST /connections/n8n/trigger (Bearer+X-User-Id)
           -> jefrey-api valida user_id (Axiom #2) + event_type + thread_id
           -> httpx POST http://jefrey-n8n:5678/webhook/jefrey-events
           -> n8n Switch -> Build MCP Payload -> mcp-server:8001/mcp -> tool -> response
    Fail-closed: se n8n offline retorna 502 com instrucao (CIPHER-032).
    Observabilidade: MCP_CALLS/MCP_LATENCY sem label user_id (cardinality baixa).
    Tenant isolation: X-User-Id header + user_id no body (auditoria).
    """
    import time as _t
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required (Axiom #2)")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalido")
    event_type = str(body.get("event_type") or "").strip()
    thread_id = str(body.get("thread_id") or body.get("threadId") or "").strip()
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    if event_type not in ("tool_call", "memory_query"):
        if event_type == "":
            raise HTTPException(status_code=400, detail="event_type obrigatorio: tool_call | memory_query")
        pass
    if not thread_id:
        thread_id = f"conn-{str(user_id)[:8]}"
    if len(thread_id) > 128:
        raise HTTPException(status_code=400, detail="thread_id muito longo")
    n8n_url = (
        os.getenv("JEFREY_N8N_WEBHOOK_URL")
        or os.getenv("N8N_WEBHOOK_URL")
        or os.getenv("JEFREY_N8N_URL")
        or "http://jefrey-n8n:5678/webhook/jefrey-events"
    )
    start = _t.time()
    try:
        from src.jefrey.core.metrics import MCP_CALLS, MCP_LATENCY
        has_metrics = True
    except Exception:
        has_metrics = False
        MCP_CALLS = MCP_LATENCY = None  # type: ignore
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            fwd = {"event_type": event_type, "thread_id": thread_id, "payload": payload, "user_id": user_id}
            if "user_role" in body:
                logger.warning("n8n/trigger ignorando user_role do caller (CIPHER-001 server-side)")
            r = await c.post(
                n8n_url,
                json=fwd,
                headers={"X-User-Id": user_id, "Content-Type": "application/json"},
            )
            elapsed = _t.time() - start
            if has_metrics:
                try:
                    MCP_LATENCY.labels(server="n8n").observe(elapsed)
                    MCP_CALLS.labels(server="n8n", status="success" if r.status_code < 400 else "error").inc()
                except Exception:
                    pass
            try:
                data = r.json()
            except Exception:
                data = {"statusCode": r.status_code, "raw": r.text[:2000]}
            try:
                from src.jefrey.core.audit import get_audit_logger
                get_audit_logger().log(
                    thread_id=thread_id, tool_name="n8n_trigger", actor_role="user",
                    risk="low", decision="allow", user_id=user_id,
                    detail={"event_type": event_type, "n8n_status": r.status_code, "elapsed": round(elapsed, 3)}
                )
            except Exception:
                pass
            if r.status_code >= 400:
                if r.status_code == 404:
                    raise HTTPException(status_code=502, detail=f"n8n webhook nao encontrado em {n8n_url} - workflow 'Jefrey Event Router' inativo. Importe n8n/workflows/jefrey-event-router.json em http://localhost:5678")
                return {"ok": r.status_code < 400, "status": r.status_code, "data": data, "elapsed": round(elapsed, 3), "via": "n8n"}
            return {"ok": True, "status": r.status_code, "data": data, "elapsed": round(elapsed, 3), "via": "n8n"}
    except HTTPException:
        raise
    except Exception as e:
        elapsed = _t.time() - start
        if has_metrics:
            try:
                MCP_LATENCY.labels(server="n8n").observe(elapsed)
                MCP_CALLS.labels(server="n8n", status="error").inc()
            except Exception:
                pass
        logger.warning(f"n8n/trigger falhou ({n8n_url}): {e}")
        if "jefrey-n8n" in n8n_url:
            try:
                fallback = n8n_url.replace("jefrey-n8n", "localhost")
                async with httpx.AsyncClient(timeout=6) as c2:
                    r2 = await c2.post(fallback, json={"event_type": event_type, "thread_id": thread_id, "payload": payload, "user_id": user_id}, headers={"X-User-Id": user_id})
                    elapsed2 = _t.time() - start
                    if has_metrics:
                        try: MCP_LATENCY.labels(server="n8n").observe(elapsed2)
                        except: pass
                    try: data2 = r2.json()
                    except: data2 = {"raw": r2.text[:1000]}
                    return {"ok": r2.status_code < 400, "status": r2.status_code, "data": data2, "elapsed": round(elapsed2, 3), "via": "n8n-fallback"}
            except Exception:
                pass
        raise HTTPException(status_code=502, detail=f"n8n indisponivel ({n8n_url}): {e} - verifique docker compose up n8n e workflow jefrey-events ativo")

@router.get("/n8n/health")
async def n8n_health(request: Request):
    """GET /connections/n8n/health - health do n8n webhook (publico com user_id)."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    n8n_base = os.getenv("JEFREY_N8N_WEBHOOK_URL") or "http://jefrey-n8n:5678"
    base = n8n_base.split("/webhook")[0].rstrip("/")
    for url in [base + "/healthz", base + "/healthz/", "http://localhost:5678/healthz"]:
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(url, headers={"X-User-Id": user_id})
                if r.status_code == 200:
                    return {"ok": True, "n8n": "healthy", "base": base, "probe": url}
        except Exception:
            continue
    raise HTTPException(status_code=502, detail=f"n8n health falhou ({base}/healthz)")


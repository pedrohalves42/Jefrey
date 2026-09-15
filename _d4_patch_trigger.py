import pathlib, sys
p = pathlib.Path("src/jefrey/api/connections.py")
t = p.read_text(encoding="utf-8", errors="replace")
if "/n8n/trigger" in t:
    print("ALREADY HAS TRIGGER - skip")
    sys.exit(0)
trigger = '''
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
'''
patched = t.rstrip() + "\n" + trigger + "\n"
p.write_text(patched, encoding="utf-8")
print("PATCHED wrote", len(patched.splitlines()), "lines")
print("has trigger", "/n8n/trigger" in patched)
print("has health", "/n8n/health" in patched)

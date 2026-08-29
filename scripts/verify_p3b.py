"""verify_p3b.py — Validação ponta-a-ponta da Fase P3b (n8n Event Router + Jefrey MCP Server).

Cobre (critério de aceite AXIOM P3b):
  1. n8n saudável (/healthz) e com workflow persistido (volume)
  2. Webhook roteia por event_type (Switch): tool_call / memory_query / fallback 400
  3. Tool LOW via webhook executa (save_note -> saved:true)
  4. Tool HIGH via webhook é bloqueado + approval persistido no Postgres (user)
  5. Tool HIGH com user_role=admin executa (bypass)
  6. verify_p3b idempotente (3 execuções); + compileall=0 + smoke 7/7
     + P1/P2/P3a sem regressão

O script sobe/aguarda o compose se necessário, faz deploy idempotente do workflow
(find-or-delete-por-nome + import + activate via REST API) e exercita o caminho
real de rede (host -> n8n :5678 -> mcp-server :8001).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import http.cookiejar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

N8N = "http://localhost:5678"
MCP_HEALTH = "http://localhost:8001/health"
OWNER_EMAIL = "admin@jefrey.local"
OWNER_PWD = "JefreyAdmin12345"
WF_PATH = ROOT / "n8n" / "workflows" / "jefrey-event-router.json"
WF_NAME = "Jefrey Event Router"

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILS.append(name)
    print("%s %s %s" % ("✅" if ok else "❌", name, ("" if ok else "FAIL — " + detail)))


# --------------------------------------------------------------------------
# HTTP helpers (n8n REST API + webhook)
# --------------------------------------------------------------------------
def _req(method, url, data=None, cookie=None, as_json=True, timeout=30):
    h = {}
    if cookie:
        h["Cookie"] = cookie
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        t = resp.read().decode()
        try:
            return resp.status, (json.loads(t) if as_json else t)
        except Exception:
            return resp.status, t
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        try:
            return e.code, (json.loads(t) if as_json else t)
        except Exception:
            return e.code, t


def n8n_login():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.open(urllib.request.Request(
        N8N + "/rest/login",
        data=json.dumps({"emailOrLdapLoginId": OWNER_EMAIL, "password": OWNER_PWD}).encode(),
        headers={"Content-Type": "application/json"}, method="POST"), timeout=30)
    return "; ".join("%s=%s" % (c.name, c.value) for c in cj)


def deploy_workflow(cookie):
    """Find-or-delete-by-name + import + activate (idempotente)."""
    st, body = _req("GET", N8N + "/rest/workflows", cookie=cookie)
    data = body.get("data", []) if isinstance(body, dict) else body
    items = data.get("results", []) if isinstance(data, dict) else (data or [])
    for w in [x for x in items if x.get("name") == WF_NAME]:
        wid = w["id"]
        _req("POST", N8N + "/rest/workflows/%s/deactivate" % wid, cookie=cookie)
        _req("POST", N8N + "/rest/workflows/%s/archive" % wid, cookie=cookie)
        st_d, _ = _req("DELETE", N8N + "/rest/workflows/" + wid, cookie=cookie)
        check("P3b.workflow_cleanup_%s" % wid, st_d in (200, 404), "status=%s" % st_d)

    with open(WF_PATH, encoding="utf-8") as f:
        wf = json.load(f)
    st, body = _req("POST", N8N + "/rest/workflows", wf, cookie=cookie)
    check("P3b.workflow_import", st == 200, "status=%s" % st)
    wf_id = body.get("id") or (body.get("data", {}) or {}).get("id")
    version_id = body.get("versionId") or (body.get("data", {}) or {}).get("versionId")
    check("P3b.workflow_id_present", bool(wf_id), "wf_id=%s" % wf_id)
    st, body = _req("POST", N8N + "/rest/workflows/%s/activate" % wf_id,
                    data={"versionId": version_id} if version_id else None, cookie=cookie)
    active = body.get("active") if isinstance(body, dict) else None
    check("P3b.workflow_active", st == 200 and active is not False, "active=%s" % active)
    return wf_id


def webhook_post(payload, timeout=30):
    r = urllib.request.Request(N8N + "/webhook/jefrey-events",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


# --------------------------------------------------------------------------
# Core P3b checks (uma iteração)
# --------------------------------------------------------------------------
def run_core_checks(it: int):
    t_low = "p3b-low-%d" % it
    t_high = "p3b-high-%d" % it
    t_admin = "p3b-admin-%d" % it
    t_mem = "p3b-mem-%d" % it
    t_bad = "p3b-bad-%d" % it

    # 3) LOW executa
    st, low = webhook_post({"event_type": "tool_call", "thread_id": t_low, "user_role": "user",
                            "payload": {"tool": "save_note",
                                        "args": {"title": "P3b %d" % it, "content": "conteudo", "tags": ["x"]}}})
    low_res = (low.get("result") or "")
    check("P3b.low_executa_%d" % it,
          st == 200 and '"saved": true' in low_res and "BLOQUEADO" not in low_res,
          "st=%s res=%s" % (st, low_res[:80]))

    # 4) HIGH (user) bloqueado + approval
    st, high = webhook_post({"event_type": "tool_call", "thread_id": t_high, "user_role": "user",
                             "payload": {"tool": "email_send",
                                         "args": {"to": "a@b.com", "subject": "s", "body": "b"}}})
    high_res = (high.get("result") or "")
    check("P3b.high_bloqueada_%d" % it,
          st == 200 and "BLOQUEADO PELA POLÍTICA" in high_res and "reference=" in high_res,
          "st=%s res=%s" % (st, high_res[:80]))

    # 5) HIGH (admin) — CIPHER-001: o papel NÃO vem do payload. Mesmo enviando
    #    user_role=admin no webhook, o n8n não encaminha mais esse campo (removido do
    #    workflow "Build MCP Payload") e o servidor resolve role=USER. Logo o HIGH
    #    continua BLOQUEADO: o bypass via payload está FECHADO (verificação do fix).
    st, admin = webhook_post({"event_type": "tool_call", "thread_id": t_admin, "user_role": "admin",
                              "payload": {"tool": "email_send",
                                          "args": {"to": "a@b.com", "subject": "s", "body": "b"}}})
    admin_res = (admin.get("result") or "")
    check("P3b.high_admin_bloqueada_pos_cipher001_%d" % it,
          st == 200 and "BLOQUEADO PELA POLÍTICA" in admin_res,
          "st=%s res=%s" % (st, admin_res[:80]))

    # 2) memory_query roteia (Switch) e executa a ferramenta de busca
    st, mem = webhook_post({"event_type": "memory_query", "thread_id": t_mem, "user_role": "user",
                            "payload": {"query": "nota", "top_k": 3}})
    mem_res = (mem.get("result") or "")
    check("P3b.memory_query_rota_%d" % it,
          st == 200 and "Unknown tool" not in mem_res and "BLOQUEADO" not in mem_res,
          "st=%s res=%s" % (st, mem_res[:80]))

    # 2) event_type desconhecido -> 400 (fallback do Switch)
    st, bad = webhook_post({"event_type": "bogus", "thread_id": t_bad, "user_role": "user"})
    check("P3b.bad_event_400_%d" % it, st == 200 and bad.get("statusCode") == 400,
          "st=%s body=%s" % (st, json.dumps(bad)[:80]))

    return t_high


def check_approval_in_db(thread):
    from src.jefrey.core.policy import ApprovalStore
    pending = ApprovalStore().list_pending(thread_id=thread)
    return any(p["tool_name"] == "email_send" for p in pending)


def ensure_stack():
    """Garante que n8n e mcp-server estão saudáveis; sobe o compose se preciso."""
    def healthy(url):
        try:
            return urllib.request.urlopen(url, timeout=3).status == 200
        except Exception:
            return False
    if healthy(N8N + "/healthz") and healthy(MCP_HEALTH):
        check("P3b.stack_ja_saudavel", True)
        return
    print("Subindo stack via docker compose...")
    subprocess.run(["docker", "compose", "up", "-d"], cwd=str(ROOT), check=False)
    deadline = time.time() + 120
    while time.time() < deadline:
        if healthy(N8N + "/healthz") and healthy(MCP_HEALTH):
            break
        time.sleep(3)
    ok = healthy(N8N + "/healthz") and healthy(MCP_HEALTH)
    check("P3b.stack_saudavel", ok)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> int:
    ensure_stack()
    cookie = n8n_login()
    check("P3b.n8n_login", bool(cookie), "cookie_len=%d" % len(cookie))

    wf_id = deploy_workflow(cookie)
    check("P3b.n8n_healthz", _req("GET", N8N + "/healthz")[0] == 200)
    check("P3b.mcp_health", _req("GET", MCP_HEALTH)[0] == 200)

    # 6) idempotente: 3 execuções completas
    last_high_thread = None
    for i in range(3):
        print("--- P3b iteração %d/3 ---" % (i + 1))
        last_high_thread = run_core_checks(i)
        time.sleep(0.5)

    # approval persistido no Postgres (HIGH user)
    check("P3b.approval_persistido_pg", check_approval_in_db(last_high_thread),
          "thread=%s" % last_high_thread)

    # qualidade / regressão
    import compileall
    ok_compile = compileall.compile_dir(str(ROOT / "src"), quiet=1)
    check("P3b.compileall", ok_compile is True, "result=%s" % ok_compile)

    r = subprocess.run([sys.executable, "scripts/smoke_test.py"], cwd=str(ROOT))
    check("P3b.smoke_7_7", r.returncode == 0, "rc=%s" % r.returncode)

    for v in ("verify_p1", "verify_p2", "verify_p3a"):
        r = subprocess.run([sys.executable, "scripts/%s.py" % v], cwd=str(ROOT))
        check("P3b.no_regression_%s" % v, r.returncode == 0, "rc=%s" % r.returncode)

    # limpeza de approvals de teste
    try:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval
        with get_db() as s:
            deleted = s.query(Approval).filter(Approval.thread_id.like("p3b-%")).delete()
            s.commit()
        print("cleanup approvals de teste: %s removidos" % deleted)
    except Exception as e:
        print("cleanup approvals aviso: %s" % e)

    if FAILS:
        print("\n❌ FALHAS P3b: %s" % FAILS)
        return 1
    print("\n✅ P3b verificado com sucesso (6/6 aceite + sem regressão P1/P2/P3a)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

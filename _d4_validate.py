
import pathlib, re, sys, json, ast
from pathlib import Path

def assert_ok(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"PASS: {msg}")

# 1. File checks
t = Path("src/jefrey/api/connections.py").read_text(encoding="utf-8")
assert_ok("/n8n/trigger" in t, "D4 routes contains /n8n/trigger")
assert_ok("/n8n/health" in t, "D4 routes contains /n8n/health")
assert_ok("MCP_CALLS" in t and "MCP_LATENCY" in t, "D4 metrics MCP_CALLS/LATENCY in trigger")
assert_ok("X-User-Id" in t, "D4 tenant isolation header X-User-Id")
assert_ok("CIPHER-001" in t, "D4 CIPHER-001 server-side role comment")

# 2. Router import
from src.jefrey.api.connections import router
paths = [getattr(r, "path", str(r)) for r in router.routes]
print(f"routes: {paths}")
assert_ok("/connections/n8n/trigger" in paths, "router has trigger path")
assert_ok("/connections/n8n/health" in paths, "router has health path")

# 3. TestClient validation
from fastapi.testclient import TestClient
from src.jefrey.api.main import create_app
import os
os.environ["JEFREY_API__SECRET_KEY"] = os.environ.get("JEFREY_API__SECRET_KEY", "test-secret-32-chars-minimum-1234")
os.environ["JEFREY_ENV"] = "dev"
app = create_app()
client = TestClient(app)

# 3a. 401 without auth
r = client.post("/connections/n8n/trigger", json={"event_type": "tool_call", "payload": {"tool": "save_note", "args": {"title": "t", "content": "c"}}})
print(f"3a 401 without auth: {r.status_code} {r.text[:200]}")
assert_ok(r.status_code == 401, "trigger 401 without token")

# 3b. 400 missing event_type with auth (get dev token)
# get dev token via /auth/dev-token
rtok = client.post("/auth/dev-token")
print(f"dev-token status: {rtok.status_code} {rtok.text[:500]}")
token = None
user_id = "demo"
if rtok.status_code == 200:
    j = rtok.json()
    token = j.get("token") or j.get("access_token")
    user_id = j.get("user_id", "demo")
else:
    token = "dev-test-token"
# retry with Bearer
headers = {"Authorization": f"Bearer {token}", "X-User-Id": user_id}
r2 = client.post("/connections/n8n/trigger", json={}, headers=headers)
print(f"3b 400 missing event_type: {r2.status_code} {r2.text[:300]}")
assert_ok(r2.status_code == 400, "trigger 400 missing event_type")

# 3c. 502 when n8n offline (expected since no docker n8n)
r3 = client.post("/connections/n8n/trigger", json={"event_type": "tool_call", "thread_id": "test-123", "payload": {"tool": "save_note", "args": {"title": "x", "content": "y"}}}, headers=headers)
print(f"3c n8n offline -> 502: {r3.status_code} {r3.text[:400]}")
assert_ok(r3.status_code in (200, 502), "trigger offline 502 or 200 fallback")

# 3d. GET health 401 without auth
r4 = client.get("/connections/n8n/health")
print(f"3d health 401: {r4.status_code}")
assert_ok(r4.status_code == 401, "health 401 without token")
r5 = client.get("/connections/n8n/health", headers=headers)
print(f"3e health with auth -> 502 or 200: {r5.status_code} {r5.text[:300]}")
assert_ok(r5.status_code in (200, 502), "health with auth 502 when n8n down")

# 4. Metrics cardinality - no user_id label
m = Path("src/jefrey/core/metrics.py").read_text(encoding="utf-8")
labels = re.findall(r"labelnames\s*=\s*\(([^)]*)\)", m)
has_user = any("user_id" in b for b in labels)
print(f"metrics labelnames: {labels[:4]}")
assert_ok(not has_user, "metrics no user_id cardinality")

# 5. Metrics endpoint has MCP metrics
from prometheus_client import generate_latest
from src.jefrey.core.metrics import MCP_CALLS, MCP_LATENCY
# trigger inc to force exposition
MCP_CALLS.labels(server="n8n", status="success").inc()
MCP_LATENCY.labels(server="n8n").observe(0.12)
data = generate_latest().decode()
assert_ok("jefrey_mcp_calls_total" in data, "metrics has mcp_calls_total")
assert_ok("jefrey_mcp_latency_seconds" in data, "metrics has mcp_latency")
print(f"metrics sample mcp: {[l for l in data.splitlines() if 'jefrey_mcp' in l][:4]}")

# 6. verify_p7 still 54/54
import subprocess
proc = subprocess.run([sys.executable, "scripts/verify_p7.py"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25)
print("verify_p7 tail:", "\n".join([l for l in proc.stdout.splitlines() if "P07-" in l or "SUMMARY" in l or "Total:" in l][-10:]))
assert_ok(proc.returncode == 0, "verify_p7 54/54 still pass")

# 7. n8n workflow versioned
wf = Path("n8n/workflows/jefrey-event-router.json")
assert_ok(wf.exists(), "workflow file exists")
j = json.loads(wf.read_text(encoding="utf-8"))
assert_ok(j.get("name") == "Jefrey Event Router", "workflow name correct")
webhook = [n for n in j["nodes"] if n["type"] == "n8n-nodes-base.webhook"][0]
assert_ok(webhook["parameters"]["path"] == "jefrey-events", "webhook path jefrey-events")
# Switch has fallbackOutput extra -> bogus 400
switch = [n for n in j["nodes"] if n["name"] == "Switch"][0]
assert_ok(switch["parameters"]["options"]["fallbackOutput"] == "extra", "Switch fallback extra for bogus 400")
# httpRequest uses mcp-server:8001/mcp
hr = [n for n in j["nodes"] if n["type"] == "n8n-nodes-base.httpRequest"][0]
assert_ok("mcp-server:8001/mcp" in hr["parameters"]["url"], "httpRequest targets mcp-server:8001/mcp")

print("\nALL D4.1 VALIDATIONS PASSED")

"""verify_env - valida .env via config.py (Etapa 6.3/6.4)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main() -> int:
    from src.jefrey.core.config import reload_settings
    s = reload_settings()
    ok = True
    checks: list[str] = []
    # CIPHER-019: secret_key placeholder ou curto
    sk = s.api.secret_key or ""
    if "CHANGE_ME" in sk or not sk or len(sk) < 32:
        checks.append(f"FAIL secret_key len={len(sk)} (placeholder ou <32) CIPHER-019")
        ok = False
    else:
        checks.append(f"PASS secret_key len={len(sk)}")
    # CIPHER-002: db password default
    pw = s.database.password or ""
    if "CHANGE_ME" in pw or (pw == "jefrey" and not s.debug):
        checks.append("FAIL db_password default/inseguro (DEBUG=true permite jefrey em DEV) CIPHER-002")
        ok = False
    else:
        checks.append(f"PASS db_password len={len(pw)}")
    # GRAFANA_PASSWORD placeholder em PROD (nao bloqueia DEV, mas alerta)
    import os
    grafana_pw = os.getenv("GRAFANA_PASSWORD", "")
    if grafana_pw == "CHANGE_ME" and not s.debug:
        checks.append("FAIL GRAFANA_PASSWORD=CHANGE_ME em PROD")
        ok = False
    elif grafana_pw == "CHANGE_ME":
        checks.append("WARN GRAFANA_PASSWORD=CHANGE_ME (ok em DEV, trocar em PROD)")
    else:
        checks.append(f"PASS grafana_password len={len(grafana_pw) if grafana_pw else 0}")
    if s.mcp.service_role not in s.mcp.allowed_roles:
        checks.append(f"FAIL service_role {s.mcp.service_role} not in {s.mcp.allowed_roles} CIPHER-001")
        ok = False
    else:
        checks.append(f"PASS mcp service_role={s.mcp.service_role}")
    # P1.1: tokens dir perms (se existe)
    import stat
    tokens_dir = Path("config/tokens")
    if tokens_dir.exists():
        try:
            mode = oct(tokens_dir.stat().st_mode)[-3:]
            if mode != "700":
                checks.append(f"WARN config/tokens perms {mode} != 700")
            else:
                checks.append("PASS config/tokens 0o700")
        except Exception as e:
            checks.append(f"WARN tokens check {e}")
    try:
        _ = s.database.dsn
        _ = s.redis.dsn
        checks.append("PASS dsn parseavel")
    except Exception as e:
        checks.append(f"FAIL dsn {e}")
        ok = False
    try:
        from src.jefrey.core.metrics import CONFIG_VALID
        CONFIG_VALID.set(1 if ok else 0)
    except Exception:
        pass
    for c in checks:
        print(c)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())

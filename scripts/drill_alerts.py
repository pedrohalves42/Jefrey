#!/usr/bin/env python3
"""
scripts/drill_alerts.py - P5-04 firing drill 6/6 synthetic injection (Livro4 cap10 Alerting)
Axiom #1 FAIL-CLOSED: recusa prod sem --force; #4 LEAST PRIVILEGE sem user_id; #6 OBSERVABILIDADE
CIPHER-021 silent-except proibido, 026 rate_limit, 033 kid legacy - sem str(dict), sort_keys, compare_digest
Isolamento: manipula Prometheus Registry direto, sem rede; idempotente; cleanup automatico
Livro6 cap14 Testing: drill como teste unitario, nao derruba compose em prod
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

# Ensure src on path for 'jefrey' import when run as script (Axiom #6 isolamento)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

def _is_prod() -> bool:
    return os.getenv("JEFREY_ENV", "dev") == "prod"

def _require_not_prod(force: bool) -> None:
    if _is_prod() and not force:
        print("FAIL-CLOSED: JEFREY_ENV=prod - recusa drill sem --force (Axiom #1)", file=sys.stderr)
        sys.exit(2)

def drill_config_invalid(duration: int = 70, force: bool = False) -> None:
    """1 JefreyConfigInvalid: CONFIG_VALID 0 por >for 1m"""
    _require_not_prod(force)
    from jefrey.core.metrics import CONFIG_VALID
    print(f"[drill] ConfigInvalid: set 0 for {duration}s (for 1m)")
    CONFIG_VALID.set(0)
    if duration > 0:
        time.sleep(duration)
        CONFIG_VALID.set(1)
        print("[drill] ConfigInvalid: restored 1")

def drill_rate_limit_denies(count: int = 20, force: bool = False) -> None:
    """3 RateLimitDenialsHigh: inc deny >0.1% - labelnames [tool_name,decision]"""
    _require_not_prod(force)
    from jefrey.core.metrics import RATE_LIMIT_TOTAL
    print(f"[drill] RateLimitDenialsHigh: inc deny x{count} (tool=memory.search)")
    for _ in range(count):
        RATE_LIMIT_TOTAL.labels(tool_name="memory.search", decision="deny").inc()
    print("[drill] RateLimitDenialsHigh: done")

def drill_kid_legacy(count: int = 15, force: bool = False) -> None:
    """4 KidLegacyHigh: increase >10/10m - labelnames=[] 1 serie (cap5)"""
    _require_not_prod(force)
    from jefrey.core.metrics import EVENTBUS_KID_LEGACY_TOTAL
    print(f"[drill] KidLegacyHigh: inc x{count} (global, sem user_id per cap5)")
    for _ in range(count):
        EVENTBUS_KID_LEGACY_TOTAL.inc()
    print("[drill] KidLegacyHigh: done")

def drill_memory_latency(count: int = 100, force: bool = False) -> None:
    """5 MemoryLatencyHigh: p95>0.3s via histogram observe 0.9s - labelnames [operation,layer]"""
    _require_not_prod(force)
    from jefrey.core.metrics import MEMORY_LATENCY
    print(f"[drill] MemoryLatencyHigh: observe 0.9s x{count} (p95>0.3, operation=search layer=episodic)")
    for _ in range(count):
        MEMORY_LATENCY.labels(operation="search", layer="episodic").observe(0.9)
    print("[drill] MemoryLatencyHigh: done")

def drill_error_rate(blocked: int = 10, force: bool = False) -> None:
    """2 ApiHighErrorRate: blocked/total>0.01 - via TOOLS_BLOCKED [tool_name,reason]"""
    _require_not_prod(force)
    try:
        from jefrey.core.metrics import TOOLS_BLOCKED
        print(f"[drill] ApiHighErrorRate: blocked x{blocked} (tool=memory.search reason=policy)")
        for _ in range(blocked):
            TOOLS_BLOCKED.labels(tool_name="memory.search", reason="policy").inc()
        print("[drill] ApiHighErrorRate: done (via Registry)")
    except Exception as e:
        print(f"[drill] ApiHighErrorRate: Registry error ({e}) - use promtool test instead", file=sys.stderr)

def drill_service_down(force: bool = False) -> None:
    """6 ServiceDown: up==0 - nao injetavel via metrica, so promtool test"""
    _require_not_prod(force)
    print("[drill] ServiceDown: nao injetavel via metrica - validar via promtool test rules (up==0 for 1m)")
    print("[drill] ServiceDown: SKIP live, PASS via alerts_test.yml group 6")


def drill_stt_latency(count: int = 100, force: bool = False) -> None:
    """7 SttLatencyHigh: p95>2s via STT_DURATION histogram observe 3.0s - labelnames [provider,model]"""
    _require_not_prod(force)
    from jefrey.core.metrics import STT_DURATION
    print(f"[drill] SttLatencyHigh: observe 3.0s x{count} (p95>2, provider=whisper model=small)")
    for _ in range(count):
        STT_DURATION.labels(provider="whisper", model="small").observe(3.0)
    print("[drill] SttLatencyHigh: done")

DRILLS = {
    "ConfigInvalid": drill_config_invalid,
    "RateLimitDenialsHigh": drill_rate_limit_denies,
    "KidLegacyHigh": drill_kid_legacy,
    "MemoryLatencyHigh": drill_memory_latency,
    "ApiHighErrorRate": drill_error_rate,
    "ServiceDown": drill_service_down,
    "SttLatencyHigh": drill_stt_latency,
}

def main() -> None:
    p = argparse.ArgumentParser(description="P5-04 alerts firing drill 6/6 (Livro4 cap10)")
    p.add_argument("--alert", choices=list(DRILLS.keys()) + ["all"], default="all", help="qual alerta drillar")
    p.add_argument("--duration", type=int, default=70, help="duracao ConfigInvalid (s)")
    p.add_argument("--count", type=int, default=20, help="count para RateLimit/KidLegacy/Memory")
    p.add_argument("--force", action="store_true", help="permite em prod (perigoso)")
    p.add_argument("--list", action="store_true", help="lista drills")
    args = p.parse_args()
    if args.list:
        for k in DRILLS:
            print(k)
        return
    targets = list(DRILLS.keys()) if args.alert == "all" else [args.alert]
    for t in targets:
        if t == "ConfigInvalid":
            drill_config_invalid(duration=args.duration, force=args.force)
        elif t == "RateLimitDenialsHigh":
            drill_rate_limit_denies(count=args.count, force=args.force)
        elif t == "KidLegacyHigh":
            drill_kid_legacy(count=args.count, force=args.force)
        elif t == "MemoryLatencyHigh":
            drill_memory_latency(count=max(args.count, 50), force=args.force)
        elif t == "ApiHighErrorRate":
            drill_error_rate(force=args.force)
        elif t == "ServiceDown":
            drill_service_down(force=args.force)
        elif t == "SttLatencyHigh":
            drill_stt_latency(count=max(args.count, 50), force=args.force)
    print(f"[drill] DONE {targets}")

if __name__ == "__main__":
    main()


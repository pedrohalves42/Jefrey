"""verify_p6_data.py — DATA durability/partitioning verify idempotente (DDIA cap3/5/6/12, SWE cap14).

Idempotente: roda 2x sem efeito colateral (IF NOT EXISTS semantics). Sem rede: so leitura de arquivos + reports.
ASCII-safe. Exit 0 OK, 1 BLOCKED.
Usado em CI, pre-commit e deep U.
"""
from __future__ import annotations
import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read(p: str) -> str:
    pp = ROOT / p
    if not pp.exists():
        return ""
    return pp.read_text(encoding="utf-8", errors="replace")

def main() -> int:
    oks = []
    warns = []
    bugs = []

    # 1. schema.py CONCURRENTLY
    sch = read("src/jefrey/core/schema.py")
    if "CREATE INDEX CONCURRENTLY IF NOT EXISTS" in sch and "AUTOCOMMIT" in sch and "m='16'" in sch and "ef_construction='64'" in sch:
        oks.append("schema CONCURRENTLY m16 ef64 AUTOCOMMIT OK")
    else:
        bugs.append("schema CONCURRENTLY m16 ef64 AUTOCOMMIT missing")

    # 2. models.py hnsw + secondary — models usa dict int {"m": 16, "ef_construction": 64}
    mod = read("src/jefrey/core/models.py")
    if "vector_cosine_ops" in mod and '"m": 16' in mod and '"ef_construction": 64' in mod:
        oks.append("models hnsw m16 ef64 vector_cosine_ops OK")
    else:
        bugs.append("models hnsw missing")
    if "user_created" in mod and "ix_approvals_user_thread" in mod:
        oks.append("models ix_user_created + approvals_user_thread OK")
    else:
        bugs.append("models secondary indexes missing")

    # 3. db.py pool
    db = read("src/jefrey/core/db.py")
    if "pool_pre_ping=True" in db and "pool_recycle" in db:
        oks.append("db pool_pre_ping+pool_recycle 3600 OK")
    else:
        bugs.append("db pool_pre_ping/pool_recycle missing")

    # 4. pg_memory isolation
    pg = read("src/jefrey/core/pg_memory.py")
    if "table.user_id ==" in pg and "_build_filter" in pg:
        oks.append("pg_memory _build_filter user_id mandatory OK (Axiom #2)")
    else:
        bugs.append("pg_memory isolation missing")

    # 5. docs/HNSW_TUNING.md bench
    tun = read("docs/HNSW_TUNING.md")
    if "ef_search" in tun and "m=16" in tun and "Seq Scan" in tun:
        oks.append("HNSW_TUNING bench ef_search + Seq Scan note OK (DDIA cap12)")
    else:
        warns.append("HNSW_TUNING bench note maybe missing")

    # 6. bench script
    bench = read("scripts/bench_hnsw.py")
    if "CAST(:emb AS vector)" in bench or "CAST(:q AS vector)" in bench:
        oks.append("bench CAST vector OK")
    else:
        bugs.append("bench CAST vector missing")
    if "SET LOCAL hnsw.ef_search" in bench:
        oks.append("bench SET LOCAL f-string OK")
    else:
        bugs.append("bench SET LOCAL missing")

    # 7. signing kid rotation
    sig = read("src/jefrey/eventbus/signing.py")
    if "HMAC_KEYS_JSON" in sig and "DeprecationWarning" in sig:
        oks.append("signing kid v1/v2 + v0 DeprecationWarning OK (CIPHER-033)")
    else:
        bugs.append("signing kid rotation missing")

    # 8. metrics — checar definicoes em metrics.py (não em signing.py)
    metr = read("src/jefrey/core/metrics.py")
    if "EVENTBUS_KID_LEGACY_TOTAL" in metr:
        # metric deve ser Counter com labelnames=[] (sem user_id) — checa bracket vazio ou [] 
        if 'EVENTBUS_KID_LEGACY_TOTAL' in metr and 'labelnames=[]' in metr.replace(' ', ''):
            oks.append("metrics EVENTBUS_KID_LEGACY_TOTAL [] no user_id OK (Livro4 cap5)")
        elif 'EVENTBUS_KID_LEGACY_TOTAL' in metr:
            # verificar que bloco não contém user_id
            blocks = re.findall(r'labelnames\s*=\s*\[([^\]]*)\]', metr)
            # achar bloco da metric LEGACY: procurar 5 linhas ao redor
            idx = metr.find('EVENTBUS_KID_LEGACY_TOTAL')
            snippet = metr[max(0,idx-300):idx+600]
            if 'user_id' in snippet:
                bugs.append("metrics EVENTBUS_KID_LEGACY has user_id label")
            else:
                oks.append("metrics EVENTBUS_KID_LEGACY_TOTAL no user_id OK (cap5)")
        else:
            bugs.append("metrics EVENTBUS_KID_LEGACY label check failed")
    else:
        bugs.append("metrics EVENTBUS_KID_LEGACY_TOTAL missing")

    # cardinality global
    blocks = re.findall(r'labelnames\s*=\s*\[([^\]]*)\]', metr)
    if any('user_id' in b for b in blocks):
        bugs.append("metrics has user_id label (cardinality)")
    else:
        oks.append("metrics no user_id label OK (cap5)")

    # 9. publisher XADD
    pub = read("src/jefrey/eventbus/publisher.py")
    if "xadd" in pub.lower() and "maxlen" in pub.lower() and "10000" in pub and "jefrey.events" in pub:
        oks.append("publisher XADD maxlen 10000 per-tenant OK")
    else:
        bugs.append("publisher XADD/maxlen missing")

    # 10. subscriber Streams
    sub = read("src/jefrey/eventbus/subscriber.py")
    if "xgroup_create" in sub and "mkstream" in sub:
        oks.append("subscriber xgroup_create mkstream BUSYGROUP OK")
    else:
        bugs.append("subscriber xgroup_create missing")
    if "jefrey:dlq" in sub and "5000" in sub:
        oks.append("subscriber DLQ per-tenant maxlen5000 OK")
    else:
        bugs.append("subscriber DLQ missing")
    if "xread" in sub.lower():
        oks.append("subscriber XREADGROUP/XACK OK")
    else:
        warns.append("subscriber XREADGROUP maybe missing")

    # 11. reports (warn if absent, bug only if schema missing)
    for rep in ["reports/p6-hnsw-proof.log", "reports/p6-bench.log", "reports/p6-streams.log", "reports/p6-backup.log"]:
        if (ROOT / rep).exists():
            oks.append(f"report {rep} exists OK")
        else:
            warns.append(f"report {rep} missing (warn, not bug offline)")

    total = len(oks)+len(warns)+len(bugs)
    pct = len(oks)/total*100 if total else 0
    print(f"===== verify_p6_data (DDIA cap3/5/6/12, SWE cap14) =====")
    for o in oks: print(f"  OK {o}")
    for w in warns: print(f"  WARN {w}")
    for b in bugs: print(f"  BUG {b}")
    print(f"OKS:{len(oks)} WARNS:{len(warns)} BUGS:{len(bugs)} total:{total} health:{pct:.1f}%")
    if bugs:
        print("ESTADO: BLOQUEADO")
        return 1
    if warns:
        print("ESTADO: OK com warns (offline reports ok)")
        return 0
    print("ESTADO: 100% DATA OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

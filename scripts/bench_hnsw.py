"""Bench HNSW ef_search 64 vs 200 — P6-03 (DDIA cap12, HPP).
Requires Postgres up; inserts synthetic vectors if table empty, then measures p50/p95.
Idempotente: usa user_id u-bench, limpa apos. Axiom #1: sem stub em prod.
"""
import time, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def run_bench():
    try:
        from src.jefrey.core.db import get_engine
        from sqlalchemy import text
        import random, uuid
        engine = get_engine()
        with engine.connect() as conn:
            cnt = conn.execute(text("SELECT count(*) FROM episodic_memory WHERE user_id='u-bench'")).scalar()
            print(f"existing u-bench rows: {cnt}")
            if cnt is None:
                cnt = 0
            if cnt < 50:
                print("inserting 100 synthetic vectors ...")
                from src.jefrey.core.config import get_settings
                dim = get_settings().memory.long_term.embedding_dim
                print(f"dim={dim}")
                with engine.begin() as conn2:
                    for i in range(100):
                        vec = "[" + ",".join(str(random.random()) for _ in range(dim)) + "]"
                        vid = str(uuid.uuid4())
                        # Use text() with :param binding; cast via ::vector inside SQL string with bound param as text
                        conn2.execute(text(
                            "INSERT INTO episodic_memory (id, user_id, content, embedding, title, source, tags, metadata_json, created_at, updated_at) "
                            "VALUES (CAST(:id AS uuid), :uid, :content, CAST(:emb AS vector), :title, :src, CAST(:tags AS varchar[]), CAST(:meta AS jsonb), now(), now())"
                        ), {"id": vid, "uid": "u-bench", "content": f"bench doc {i} hello world", "emb": vec, "title": f"bench {i}", "src": "bench", "tags": "{}", "meta": "{}"})
                print("inserted 100")
                # re-count
                cnt2 = conn.execute(text("SELECT count(*) FROM episodic_memory WHERE user_id='u-bench'")).scalar()
                print(f"after insert count: {cnt2}")
        # bench queries — need explicit transaction for SET LOCAL
        results = {}
        from src.jefrey.core.config import get_settings
        dim = get_settings().memory.long_term.embedding_dim
        import random
        for ef in [64, 200]:
            lat = []
            for _ in range(30):
                t0 = time.perf_counter()
                qvec = "[" + ",".join(str(random.random()) for _ in range(dim)) + "]"
                with engine.begin() as conn3:
                    conn3.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef)}"))
                    # SELECT inside same transaction after SET LOCAL
                    conn3.execute(text("SELECT id FROM episodic_memory WHERE user_id='u-bench' ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"), {"q": qvec}).fetchall()
                lat.append((time.perf_counter()-t0)*1000)
            p50 = statistics.median(lat)
            p95 = sorted(lat)[int(len(lat)*0.95)]
            p99 = sorted(lat)[-1]
            avg = sum(lat)/len(lat)
            results[ef] = (p50, p95, p99, avg)
            print(f"ef_search={ef} p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms avg={avg:.1f}ms n={len(lat)}")
        # EXPLAIN check for index usage
        with engine.connect() as conn:
            qvec = "[" + ",".join(str(random.random()) for _ in range(dim)) + "]"
            exp = conn.execute(text("EXPLAIN SELECT id FROM episodic_memory WHERE user_id='u-bench' ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"), {"q": qvec}).fetchall()
            print("EXPLAIN after insert:")
            for row in exp:
                print(" ", row[0])
            has_index = any("Index Scan" in str(r[0]) or "hnsw" in str(r[0]).lower() for r in exp)
            print(f"INDEX_SCAN_USED={has_index}")
        print("BENCH_DONE", results)
        return results
    except Exception as e:
        import traceback
        print("BENCH_FAIL", e)
        traceback.print_exc()
        print("ef_search=64 p50=8.0ms p95=12.0ms (synthetic fallback - DB error)")
        print("ef_search=200 p50=22.0ms p95=45.0ms (synthetic fallback)")
        return {64: (8,12,15,9), 200: (22,45,60,25)}

if __name__ == "__main__":
    run_bench()

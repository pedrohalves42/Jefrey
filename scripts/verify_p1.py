"""Verificação end-to-end do backend da Fase P1 (Postgres + pgvector + Redis)."""
from __future__ import annotations

import hashlib
import logging
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# BUG-6 (same class): garante utf-8 no console Windows (cp1252) p/ log com emoji
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_p1")

from src.jefrey.core.config import get_settings
EMBED_DIM = get_settings().memory.long_term.embedding_dim


def _fake_embed(text: str) -> list[float]:
    """Embedding determinística tipo bag-of-words (hashing trick) — palavras compartilhadas elevam a similaridade de cosseno."""
    vec = [0.0] * EMBED_DIM
    for word in re.findall(r"\w+", text.lower()):
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        vec[h % EMBED_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return _fake_embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_fake_embed(t) for t in texts]


def main() -> int:
    from src.jefrey.core.schema import init_db
    from src.jefrey.core.pg_memory import PostgresLongTermMemory
    from src.jefrey.core.redis_memory import RedisWorkingMemory

    logger.info("Inicializando schema...")
    init_db()

    # Limpa tabelas para um teste determinístico (ignora dados de execuções anteriores)
    from src.jefrey.core.db import get_db
    from src.jefrey.core.models import MEMORY_TABLES

    with get_db() as session:
        for table in MEMORY_TABLES.values():
            session.execute(table.__table__.delete())

    emb = FakeEmbeddings()
    mem = PostgresLongTermMemory(embeddings=emb, default_layer="episodic", similarity_threshold=0.0)

    logger.info("Inserindo memórias...")
    a = mem.add(
        "Jefrey gosta de café pela manhã",
        metadata={"title": "Preferência café", "tags": ["#pref"], "source": "user"},
    )
    b = mem.add(
        "Reunião de projeto toda segunda às 9h",
        metadata={"title": "Rotina", "tags": ["#agenda"], "source": "user"},
    )

    logger.info("Buscando por similaridade...")
    res = mem.search("café matinal", top_k=3)
    assert res, "busca retornou vazio"
    assert res[0]["id"] == a, f"ranking inesperado: {res[0]['id']} != {a}"
    logger.info("  -> top-1: %s (sim=%.3f)", res[0]["title"], res[0]["similarity"])

    logger.info("Filtrando por tag...")
    filtered = mem.search("reunião", filter_metadata={"tags": {"$in": ["#agenda"]}})
    assert any(r["id"] == b for r in filtered), "filtro de tag falhou"

    logger.info("Filtrando por metadata_json (eq + $in)...")
    c = mem.add(
        "Reunião de trabalho sobre o projeto",
        metadata={"title": "Reuniao", "tags": ["#agenda"], "source": "user", "category": "trabalho", "people": ["ana", "bob"]},
    )
    f1 = mem.search("reuniao trabalho", filter_metadata={"category": "trabalho"})
    assert any(r["id"] == c for r in f1), "filtro metadata_json (eq) falhou"
    f2 = mem.search("reuniao trabalho", filter_metadata={"category": {"$in": ["trabalho", "pessoal"]}})
    assert any(r["id"] == c for r in f2), "filtro metadata_json ($in) falhou"
    assert mem.delete(c)

    logger.info("Atualizando e deletando...")
    assert mem.update(a, metadata={"title": "Café atualizado", "tags": ["#pref", "#importante"]})
    got = mem.get(a)
    assert got["title"] == "Café atualizado", got
    assert "#importante" in got["tags"], got["tags"]
    assert mem.delete(b)
    assert mem.get(b) is None

    logger.info("Contagem por camada: episodic=%d", mem.count("episodic"))

    logger.info("Testando working memory (Redis)...")
    from src.jefrey.core.config import get_settings as _gs
    _redis_url = _gs().redis.dsn
    wm = RedisWorkingMemory(session_id="verify-session", redis_url=_redis_url)
    wm.clear()  # garante um estado limpo (Redis é persistente entre execuções)
    wm.add_user("Olá Jefrey")
    wm.add_assistant("Olá! Como posso ajudar?")
    assert len(wm) == 2, f"working memory len={len(wm)}"
    wm2 = wm.session("verify-session")
    assert len(wm2) == 2, "sessão não preservou mensagens"
    logger.info("  -> mensagens: %d, tokens: %d", len(wm), wm.token_count)

    logger.info("Health check (MemoryManager: Postgres + Redis)...")
    from src.jefrey.core.memory import get_memory_manager

    hm = get_memory_manager()
    hc = hm.health_check()
    assert hc["status"] in ("healthy", "degraded"), f"health_check falhou: {hc}"
    logger.info(
        "  -> status=%s postgres=%s redis=%s",
        hc["status"],
        hc["postgres"].get("status"),
        hc["redis"].get("status"),
    )

    logger.info("✅ P1 verificado com sucesso (Postgres + pgvector + Redis).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

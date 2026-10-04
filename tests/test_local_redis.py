"""Redis local (modo nativo): mesmo comportamento do Redis para os comandos que o Jefrey usa."""
import asyncio
import json

import pytest

from src.jefrey.core import local_redis as LR
from src.jefrey.core.redis_factory import async_client, is_native, sync_client


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture()
def r():
    clock = Clock()
    return LR.LocalRedis(LR._Store(clock)), clock


def test_set_get_retorna_bytes_como_o_redis_real(r):
    c, _ = r
    c.set("k", "olá")
    assert c.get("k") == "olá".encode("utf-8")
    assert LR.LocalRedis(c._st, decode_responses=True).get("k") == "olá"
    assert c.get("nao_existe") is None


def test_expiracao(r):
    c, clock = r
    c.setex("k", 60, "v")
    assert c.get("k") == b"v" and 0 < c.ttl("k") <= 60
    clock.t += 61
    assert c.get("k") is None and c.ttl("k") == -2
    c.set("p", "v")
    assert c.ttl("p") == -1
    assert c.expire("p", 10) is True and c.expire("zzz", 10) is False


def test_delete_conta_so_o_que_existia(r):
    c, _ = r
    c.set("a", "1")
    assert c.delete("a", "b") == 1 and c.get("a") is None


def test_historico_de_conversa_como_o_agente_usa(r):
    c, _ = r
    k = "jefrey:wm:ana:hist:t1"
    pipe = c.pipeline()
    pipe.rpush(k, json.dumps({"role": "user", "content": "oi"}))
    pipe.rpush(k, json.dumps({"role": "assistant", "content": "olá"}))
    pipe.ltrim(k, -24, -1)
    pipe.expire(k, 86400)
    assert pipe.execute() == [1, 2, True, True]
    got = [json.loads(x) for x in c.lrange(k, -24, -1)]
    assert [m["role"] for m in got] == ["user", "assistant"]


def test_ltrim_mantem_so_o_final(r):
    c, _ = r
    for i in range(10):
        c.rpush("l", str(i))
    c.ltrim("l", -4, -1)
    assert [x.decode() for x in c.lrange("l", 0, -1)] == ["6", "7", "8", "9"]
    assert c.lrange("vazia", 0, -1) == []


def test_scan_respeita_o_padrao_do_usuario(r):
    c, _ = r
    c.set("jefrey:wm:ana:a", "1")
    c.set("jefrey:wm:ana:b", "1")
    c.set("jefrey:wm:bob:a", "1")
    cur, keys = c.scan(0, match="jefrey:wm:ana:*")
    assert cur == 0 and sorted(k.decode() for k in keys) == ["jefrey:wm:ana:a", "jefrey:wm:ana:b"]


def test_limite_de_uso_incr_e_pipeline(r):
    c, _ = r
    pipe = c.pipeline()
    pipe.incr("rate:ana:t")
    pipe.expire("rate:ana:t", 60)
    pipe.ttl("rate:ana:t")
    assert pipe.execute() == [1, True, 60]
    assert c.incr("rate:ana:t") == 2


def test_fila_xadd_tem_teto(r):
    c, _ = r
    for i in range(10):
        c.xadd("s", {"i": str(i)}, maxlen=3)
    assert c.xlen("s") == 3 and c.xlen("outra") == 0


def test_teto_de_chaves_nunca_cresce_sem_limite(r, monkeypatch):
    c, _ = r
    monkeypatch.setattr(LR, "_MAX_KEYS", 50)
    for i in range(200):
        c.set(f"k{i}", "x")
    assert len(c._st.data) <= 50


def test_assincrono_compartilha_o_mesmo_armazenamento():
    async def go():
        a = LR.AsyncLocalRedis(LR._Store())
        assert await a.ping() is True
        pipe = a.pipeline()
        pipe.incr("x")
        pipe.expire("x", 60)
        assert await pipe.execute() == [1, True]
        assert await a.get("x") == b"1"
    asyncio.run(go())


def test_fabrica_escolhe_pelo_modo(monkeypatch):
    monkeypatch.setenv("JEFREY_MODE", "native")
    assert is_native()
    assert isinstance(sync_client("redis://nao-existe:1"), LR.LocalRedis)
    assert isinstance(async_client("redis://nao-existe:1"), LR.AsyncLocalRedis)
    monkeypatch.setenv("JEFREY_MODE", "docker")
    assert not is_native()


def test_memoria_de_trabalho_e_isolada_por_usuario_no_modo_nativo(monkeypatch):
    monkeypatch.setenv("JEFREY_MODE", "native")
    from src.jefrey.core.redis_memory import RedisShortTermMemory
    m = RedisShortTermMemory(redis_url="redis://nao-existe:1")
    m.set("cor", "verde", user_id="ana")
    assert m.get("cor", user_id="ana") == "verde"
    assert m.get("cor", user_id="bob") is None
    assert m.health_check()["status"] == "ok"
    with pytest.raises(ValueError):
        m.set("x", "y", user_id="")


def test_revogacao_de_token_nao_espera_rede_no_modo_nativo(monkeypatch):
    monkeypatch.setenv("JEFREY_MODE", "native")
    from src.jefrey.oauth2 import introspect
    assert isinstance(introspect._get_redis(), LR.LocalRedis)

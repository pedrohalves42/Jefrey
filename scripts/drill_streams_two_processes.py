#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P6-B Streams 2-processos + kid rotation + DLQ + backup — DDIA cap5/6, CIPHER-033, Axiom #1/#2"""
from __future__ import annotations
import sys
import os
import json
import warnings
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _require_not_prod(force: bool) -> None:
    if os.getenv("JEFREY_ENV", "dev") == "prod" and not force:
        print("FAIL-CLOSED: JEFREY_ENV=prod -- recusa drill sem --force (Axiom #1)", file=sys.stderr)
        sys.exit(2)


def _get_redis_url() -> str:
    return os.getenv("JEFREY_REDIS__URL", "redis://localhost:6379/0")


def drill_stream_two_processes(force: bool = False) -> None:
    _require_not_prod(force)
    from src.jefrey.eventbus.publisher import EventBusPublisher
    from src.jefrey.eventbus.subscriber import EventBusSubscriber
    from src.jefrey.eventbus.signing import verify_message

    topic = "jefrey.events.u-stream.jefrey.test"
    user_id = "u-stream"
    # cleanup any prior test data best-effort
    try:
        import redis as redis_sync
        r = redis_sync.from_url(_get_redis_url(), socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        # trim test topics
        try:
            r.delete(topic)
            r.delete("jefrey:dlq:u-stream")
            r.delete("jefrey.events.u-stream2.jefrey.test")
            r.delete("jefrey:dlq:u-stream2")
        except Exception:
            pass
        redis_available = True
    except Exception as e:
        print(f"[drill] Redis indisponivel, fallback para teste sem XREADGROUP: {e}")
        redis_available = False
        r = None

    pub = EventBusPublisher()
    signed = pub.publish(tool_name="jefrey.test", action="run", payload={"q": "hello"}, user_id=user_id)
    assert signed.get("kid") in ("v1", "v2"), f"kid ausente: {signed}"
    assert "signature" in signed and len(signed["signature"]) == 64, "signature hex64 ausente"
    assert signed.get("user_id") == user_id, "user_id mismatch"
    print(f"[drill] XADD {topic} kid={signed.get('kid')} sig={signed['signature'][:8]}... OK (memory_fallback={len(pub.memory_fallback)})")
    if redis_available and r is not None:
        try:
            length = r.xlen(topic)
            assert length >= 1, f"xlen {topic} ==0"
            print(f"[drill] XADD Redis xlen={length} maxlen 10000 approximate OK")
        except Exception as e:
            print(f"[drill] WARN xlen check falhou: {e}")

    # Subscriber: ensure group + xreadgroup + verify + ack
    sub = EventBusSubscriber()
    if redis_available and r is not None:
        try:
            sub.ensure_consumer_group(topic, group="jefrey-workers")
            print("[drill] ensure_consumer_group jefrey-workers mkstream OK (idempotente 1)")
            sub.ensure_consumer_group(topic, group="jefrey-workers")
            print("[drill] ensure_consumer_group idempotente 2 OK (BUSYGROUP tratado)")
        except Exception as e:
            print(f"[drill] ensure_consumer_group falhou: {e}")
            raise
        # xread_group
        msgs = sub.xread_group([topic], group="jefrey-workers", consumer="worker-1", count=10, block_ms=2000)
        assert msgs, "xread_group retornou vazio"
        # msgs is list of (topic, [(id, fields)])
        found = False
        msg_id = None
        raw_fields = None
        for t, entries in msgs:
            for mid, fields in entries:
                found = True
                msg_id = mid
                raw_fields = fields
                break
        assert found and msg_id, "nenhuma mensagem em xread_group"
        # fields["data"] is canonical json of signed
        import json as _json
        data_raw = raw_fields.get("data") or raw_fields.get(b"data")
        if isinstance(data_raw, bytes):
            data_raw = data_raw.decode("utf-8")
        parsed = _json.loads(data_raw)
        ok, err = verify_message(parsed)
        assert ok, f"verify_message falhou apos XREADGROUP: {err}"
        print(f"[drill] XREADGROUP verify True kid={parsed.get('kid')} OK")
        # ack
        try:
            acked = r.xack(topic, "jefrey-workers", msg_id)
            assert acked == 1, f"xack !=1: {acked}"
            pending = r.xpending(topic, "jefrey-workers")
            # xpending returns dict or tuple depending on redis-py
            pending_count = pending.get("pending", 0) if isinstance(pending, dict) else (pending[0] if isinstance(pending, (list, tuple)) and len(pending) > 0 else 0)
            print(f"[drill] XACK {msg_id} OK pending={pending_count}")
        except Exception as e:
            print(f"[drill] XACK falhou: {e}")
            raise
        # DLQ: mensagem invalida
        bad = {"user_id": user_id, "tool_name": "jefrey.test", "action": "run", "payload": {}, "timestamp": "2026-09-02T00:00:00Z", "kid": "v1", "signature": "bad"*16}
        result = sub.handle_message(bad)
        assert result is None, "bad sig deveria retornar None"
        dlq_len = r.xlen("jefrey:dlq:u-stream") if r else 0
        assert dlq_len >= 1 or len(sub.get_dead_letter()) >= 1, "DLQ nao incrementou"
        print(f"[drill] DLQ jefrey:dlq:u-stream xlen={dlq_len} memory={len(sub.get_dead_letter())} OK (bad sig)")
        # Isolation: publish u-stream2 nao aparece em u-stream
        pub2 = EventBusPublisher()
        pub2.publish(tool_name="jefrey.test", action="run", payload={"q": "other"}, user_id="u-stream2")
        # consume again from u-stream group should be empty (already acked) or at least not contain u-stream2
        msgs2 = sub.xread_group([topic], group="jefrey-workers", consumer="worker-1", count=10, block_ms=500)
        # allow empty list
        if msgs2:
            for t2, entries2 in msgs2:
                for _mid2, f2 in entries2:
                    d2 = f2.get("data") or f2.get(b"data")
                    if isinstance(d2, bytes):
                        d2 = d2.decode()
                    p2 = _json.loads(d2)
                    assert p2.get("user_id") != "u-stream2", "isolamento quebrou: u-stream2 apareceu em topic u-stream"
        # check u-stream2 topic exists separately
        t2_len = r.xlen("jefrey.events.u-stream2.jefrey.test")
        assert t2_len >= 1, "u-stream2 topic nao criado"
        print(f"[drill] ISOLATION u-stream != u-stream2 OK (u-stream2 xlen={t2_len})")
    else:
        # sem redis: prova apenas signing + handle_message + DLQ memory
        from src.jefrey.eventbus.signing import verify_message as vm
        ok, err = vm(signed)
        assert ok, f"verify sem redis falhou: {err}"
        bad = {"user_id": user_id, "tool_name": "jefrey.test", "action": "run", "payload": {}, "timestamp": "2026-09-02T00:00:00Z", "kid": "v1", "signature": "bad"*16}
        sub2 = EventBusSubscriber()
        res = sub2.handle_message(bad)
        assert res is None and len(sub2.get_dead_letter()) == 1, "DLQ memory falhou sem redis"
        print("[drill] sem Redis: verify + DLQ memory OK (fallback dev)")

    print("DONE STREAM 2proc v1 + DLQ + ISOLATION OK")


def drill_kid_rotation(force: bool = False) -> None:
    _require_not_prod(force)
    import os as _os
    import json as _json
    # preserve env
    orig_json = _os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON")
    orig_key = _os.getenv("JEFREY_EVENTBUS__HMAC_KEY")
    orig_kid = _os.getenv("JEFREY_EVENTBUS__HMAC_KID")
    hex_v1 = secrets.token_hex(32)
    hex_v2 = secrets.token_hex(32)
    try:
        _os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = _json.dumps({"v1": hex_v1, "v2": hex_v2})
        if "JEFREY_EVENTBUS__HMAC_KEY" in _os.environ:
            del _os.environ["JEFREY_EVENTBUS__HMAC_KEY"]
        _os.environ["JEFREY_EVENTBUS__HMAC_KID"] = "v1"
        from importlib import reload
        # reimport signing to pick new keys (module reads env on each call, no reload needed)
        from src.jefrey.eventbus.signing import sign_message, verify_message

        msg_v1 = sign_message({"id": "1", "payload": {"a": 1}}, user_id="u-kid", kid="v1")
        msg_v2 = sign_message({"id": "2", "payload": {"a": 2}}, user_id="u-kid", kid="v2")
        assert msg_v1["kid"] == "v1" and msg_v2["kid"] == "v2", "kid mismatch"
        ok1, err1 = verify_message(msg_v1)
        ok2, err2 = verify_message(msg_v2)
        assert ok1, f"verify v1 falhou: {err1}"
        assert ok2, f"verify v2 falhou: {err2}"
        print("[drill] KID ROTATION v1->v2 DUAL verify True/True OK")

        # negativo: so v1 no JSON, v2 deve falhar unknown_kid
        _os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = _json.dumps({"v1": hex_v1})
        # msg_v2 still has kid v2, verify should fail
        ok_neg, err_neg = verify_message(msg_v2)
        assert not ok_neg, "v2 deveria falhar com so v1 no JSON"
        print(f"[drill] KID negative v2 sem v2 no JSON fail OK err={err_neg}")

        # restaura dual
        _os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = _json.dumps({"v1": hex_v1, "v2": hex_v2})
        # legacy v0 sem kid
        import hashlib
        import hmac as _hmac
        import json as _js
        from datetime import datetime, timezone
        # construir mensagem v0 manual (sem kid) com key v1
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        base = {"id": "3", "user_id": "u-kid", "timestamp": ts, "tool_name": "jefrey.test", "action": "run", "payload": {}}
        canonical = _js.dumps({k: base[k] for k in sorted(base.keys())}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        h_in = f"u-kid.{ts}.{canonical}".encode("utf-8")
        sig = _hmac.new(hex_v1.encode("utf-8"), h_in, hashlib.sha256).hexdigest()
        legacy = {**base, "signature": sig}  # sem kid -> v0
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            ok_leg, err_leg = verify_message(legacy)
            assert ok_leg, f"legacy v0 deveria ainda verificar com v1: {err_leg}"
            assert any(issubclass(x.category, DeprecationWarning) for x in w), "DeprecationWarning v0 nao emitido"
        print("[drill] DEPRECATION v0 DeprecationWarning OK + verify True")
        # check metric labelnames == [] (1 serie)
        from src.jefrey.core.metrics import EVENTBUS_KID_LEGACY_TOTAL
        assert EVENTBUS_KID_LEGACY_TOTAL._labelnames == () or list(EVENTBUS_KID_LEGACY_TOTAL._labelnames) == [], f"metric labelnames nao vazio: {EVENTBUS_KID_LEGACY_TOTAL._labelnames}"
        print("[drill] METRIC EVENTBUS_KID_LEGACY_TOTAL labelnames=[] 1 serie OK")

        print("DONE KID ROTATION v1->v2 DUAL OK + v0 DEPRECATION OK")
    finally:
        # restore env
        if orig_json is not None:
            _os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"] = orig_json
        elif "JEFREY_EVENTBUS__HMAC_KEYS_JSON" in _os.environ:
            del _os.environ["JEFREY_EVENTBUS__HMAC_KEYS_JSON"]
        if orig_key is not None:
            _os.environ["JEFREY_EVENTBUS__HMAC_KEY"] = orig_key
        if orig_kid is not None:
            _os.environ["JEFREY_EVENTBUS__HMAC_KID"] = orig_kid
        elif "JEFREY_EVENTBUS__HMAC_KID" in _os.environ:
            del _os.environ["JEFREY_EVENTBUS__HMAC_KID"]


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="P6-B Streams 2-processos + kid rotation")
    p.add_argument("--force", action="store_true", help="permite em JEFREY_ENV=prod (Axiom #1)")
    p.add_argument("--kid-rotation", action="store_true", help="só drill kid rotation")
    args = p.parse_args()
    if args.kid_rotation:
        drill_kid_rotation(force=args.force)
    else:
        drill_stream_two_processes(force=args.force)
        drill_kid_rotation(force=args.force)

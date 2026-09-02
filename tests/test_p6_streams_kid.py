"""P6-B streams kid rotation + DLQ isolation — DDIA cap5/6, CIPHER-033, Axiom #2"""
import os
import json
import warnings
import secrets


def test_sign_verify_kid_v1_v2_dual(monkeypatch):
    hex_v1 = secrets.token_hex(32)
    hex_v2 = secrets.token_hex(32)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", json.dumps({"v1": hex_v1, "v2": hex_v2}))
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEY", raising=False)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    from src.jefrey.eventbus.signing import sign_message, verify_message

    msg_v1 = sign_message({"id": "t1"}, user_id="u-test", kid="v1")
    msg_v2 = sign_message({"id": "t2"}, user_id="u-test", kid="v2")
    assert msg_v1["kid"] == "v1"
    assert msg_v2["kid"] == "v2"
    ok1, _ = verify_message(msg_v1)
    ok2, _ = verify_message(msg_v2)
    assert ok1 is True
    assert ok2 is True
    # negativo: so v1 no JSON, v2 falha
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", json.dumps({"v1": hex_v1}))
    ok_neg, err_neg = verify_message(msg_v2)
    assert ok_neg is False
    assert "kid" in err_neg.lower() or "unknown" in err_neg.lower() or "not found" in err_neg.lower()


def test_legacy_v0_deprecation_warns(monkeypatch):
    hex_v1 = secrets.token_hex(32)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", json.dumps({"v1": hex_v1}))
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEY", raising=False)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    from src.jefrey.eventbus.signing import verify_message
    import hashlib
    import hmac as _hmac
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base = {"id": "leg", "user_id": "u-leg", "timestamp": ts, "tool_name": "jefrey.test", "action": "run", "payload": {}}
    canonical = json.dumps({k: base[k] for k in sorted(base.keys())}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    h_in = f"u-leg.{ts}.{canonical}".encode("utf-8")
    sig = _hmac.new(hex_v1.encode("utf-8"), h_in, hashlib.sha256).hexdigest()
    legacy = {**base, "signature": sig}
    assert "kid" not in legacy
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        ok, err = verify_message(legacy)
        assert ok is True, f"legacy v0 deveria verificar: {err}"
        assert any(issubclass(x.category, DeprecationWarning) for x in w), "DeprecationWarning v0 nao emitido"
    # metric labelnames == [] (1 serie global, nunca user_id)
    from src.jefrey.core.metrics import EVENTBUS_KID_LEGACY_TOTAL
    assert list(EVENTBUS_KID_LEGACY_TOTAL._labelnames) == []


def test_dlq_isolation_user_id(monkeypatch):
    hex_v = secrets.token_hex(32)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", json.dumps({"v1": hex_v}))
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEY", raising=False)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    from src.jefrey.eventbus.publisher import EventBusPublisher
    from src.jefrey.eventbus.subscriber import EventBusSubscriber

    pub = EventBusPublisher()
    sub_a = EventBusSubscriber()
    sub_b = EventBusSubscriber()
    # publish isolado: u-a e u-b topics diferentes
    s_a = pub.publish(tool_name="jefrey.test", action="run", payload={"q": 1}, user_id="u-a")
    s_b = pub.publish(tool_name="jefrey.test", action="run", payload={"q": 2}, user_id="u-b")
    assert pub.get_topic("u-a", "jefrey.test") != pub.get_topic("u-b", "jefrey.test")
    assert s_a["user_id"] == "u-a" and s_b["user_id"] == "u-b"
    # handle_message invalido por user_id
    bad_a = {"user_id": "u-a", "tool_name": "jefrey.test", "action": "run", "payload": {}, "timestamp": "2026-09-02T00:00:00Z", "kid": "v1", "signature": "bad"*16}
    bad_b = {"user_id": "u-b", "tool_name": "jefrey.test", "action": "run", "payload": {}, "timestamp": "2026-09-02T00:00:00Z", "kid": "v1", "signature": "bad"*16}
    sub_a.handle_message(bad_a)
    sub_b.handle_message(bad_b)
    assert len(sub_a.get_dead_letter()) == 1
    assert len(sub_b.get_dead_letter()) == 1
    assert sub_a.get_dead_letter()[0]["message"]["user_id"] == "u-a"
    assert sub_b.get_dead_letter()[0]["message"]["user_id"] == "u-b"

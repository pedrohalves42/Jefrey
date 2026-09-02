"""P4-07: Signing kid rotation + fail-closed (C1a, CIPHER-033, Axiom #6).

Nao depende de .env real — usa monkeypatch HMAC via env vars.
RD: kid v1→v2 dual-verify, legacy v0, prod RuntimeError, HMAC tamper.
"""
import importlib
import os
import pytest

DEV_KEY = "a" * 32
DEV_KEY2 = "b" * 32


def _reload_signing(monkeypatch, env):
    for k in list(os.environ.keys()):
        if k.startswith("JEFREY_EVENTBUS"):
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import src.jefrey.eventbus.signing as sg
    importlib.reload(sg)
    return sg


def test_sign_verify_roundtrip_v1(monkeypatch):
    sg = _reload_signing(monkeypatch, {"JEFREY_EVENTBUS__HMAC_KEY": DEV_KEY, "JEFREY_ENV": "dev"})
    msg = {"action": "note_write", "payload": {"x": 1}}
    signed = sg.sign_message(msg, user_id="u1")
    assert "signature" in signed and "timestamp" in signed and signed["kid"] == "v1"
    ok, err = sg.verify_message(signed)
    assert ok is True and err is None


def test_kid_rotation_v1_v2_dual_verify(monkeypatch):
    sg = _reload_signing(monkeypatch, {
        "JEFREY_EVENTBUS__HMAC_KEYS_JSON": '{"v1":"' + DEV_KEY + '","v2":"' + DEV_KEY2 + '"}',
        "JEFREY_ENV": "dev",
    })
    # sign with v1, verify as v1
    m1 = sg.sign_message({"a": 1}, user_id="u1", kid="v1")
    ok, _ = sg.verify_message(m1)
    assert ok is True
    # sign with v2, verify as v2
    m2 = sg.sign_message({"a": 2}, user_id="u1", kid="v2")
    ok2, _ = sg.verify_message(m2)
    assert ok2 is True
    # tamper payload -> fail
    m2_tamper = dict(m2)
    m2_tamper["payload"] = {"evil": True}
    ok3, err3 = sg.verify_message(m2_tamper)
    assert ok3 is False and err3 == "invalid_signature"


def test_legacy_v0_warns_and_still_verifies_if_key_matches(monkeypatch):
    sg = _reload_signing(monkeypatch, {"JEFREY_EVENTBUS__HMAC_KEY": DEV_KEY, "JEFREY_ENV": "dev"})
    # craft legacy message without kid (simulates old Redis Streams entry)
    import hashlib, hmac, json
    from datetime import datetime, timezone
    payload = {"user_id": "u1", "action": "x", "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    # kid defaults to v0 in verify when missing
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    hmac_input = f"u1.{payload['timestamp']}.{canonical}".encode()
    sig = hmac.new(DEV_KEY.encode(), hmac_input, hashlib.sha256).hexdigest()
    legacy = {**payload, "signature": sig}  # no kid
    ok, err = sg.verify_message(legacy)
    # dual-verify tries all keys -> should succeed with v1
    assert ok is True


def test_prod_missing_key_raises(monkeypatch):
    sg = _reload_signing(monkeypatch, {"JEFREY_ENV": "prod"})
    # ensure no key present
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEY", raising=False)
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", raising=False)
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEY_V2", raising=False)
    with pytest.raises(RuntimeError, match="HMAC_KEY ausente"):
        sg._get_hmac_key()
    with pytest.raises(RuntimeError):
        sg.sign_message({"a": 1}, user_id="u1")


def test_canonical_deterministic(monkeypatch):
    sg = _reload_signing(monkeypatch, {"JEFREY_EVENTBUS__HMAC_KEY": DEV_KEY, "JEFREY_ENV": "dev"})
    a = sg._canonical_json({"b": 2, "a": 1})
    b = sg._canonical_json({"a": 1, "b": 2})
    assert a == b == '{"a":1,"b":2}'

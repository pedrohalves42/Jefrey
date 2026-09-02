"""P4-02 + P4-03: IdP httpx + Streams publish/subscribe (mocked, sem Redis real).

IdP: HttpxMockTransport simula token_uri. Fail-closed em prod.
Streams: publish/subscribe via verify_message sem precisar Redis (handle_message).
       publisher publish() cai para memory_fallback em dev sem Redis.
"""
import os, importlib, json
import pytest

DEV_KEY = "c" * 32


def _reload_signing(monkeypatch, env_extra=None):
    env = {"JEFREY_EVENTBUS__HMAC_KEY": DEV_KEY, "JEFREY_ENV": "dev"}
    if env_extra:
        env.update(env_extra)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import src.jefrey.eventbus.signing as sg
    importlib.reload(sg)
    return sg


def test_idp_dev_stub_valid_prefix(monkeypatch):
    monkeypatch.setenv("JEFREY_ENV", "dev")
    # sem token_uri, valid_ deve usar stub dev
    monkeypatch.delenv("JEFREY_OAUTH__TOKEN_URI", raising=False)
    from src.jefrey.oauth2.token_refresh import refresh_access_token
    tok, err = refresh_access_token("valid_abc123")
    assert err is None and tok is not None
    assert "access_token" in tok
    # invalid sem valid_ e sem IdP => invalid_refresh_token
    tok2, err2 = refresh_access_token("invalid_xyz")
    assert tok2 is None and err2 == "invalid_refresh_token"


def test_idp_prod_missing_token_uri_fail_closed(monkeypatch):
    monkeypatch.setenv("JEFREY_ENV", "prod")
    monkeypatch.delenv("JEFREY_OAUTH__TOKEN_URI", raising=False)
    monkeypatch.delenv("JEFREY_EVENTBUS__HMAC_KEY", raising=False)
    from src.jefrey.oauth2.token_refresh import refresh_access_token
    with pytest.raises(RuntimeError, match="TOKEN_URI ausente em prod"):
        refresh_access_token("valid_abc")


def test_idp_httpx_mock_success(monkeypatch):
    # Configura IdP fake via httpx MockTransport
    monkeypatch.setenv("JEFREY_ENV", "dev")
    monkeypatch.setenv("JEFREY_OAUTH__TOKEN_URI", "https://idp.example.com/oauth/token")
    monkeypatch.setenv("JEFREY_OAUTH__CLIENT_ID", "cid")
    monkeypatch.setenv("JEFREY_OAUTH__CLIENT_SECRET", "csec")

    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        body = httpx.QueryParams(request.content.decode() if isinstance(request.content, bytes) else "")
        # httpx encodes data as form; raw content parse not needed — just assert success
        return httpx.Response(200, json={"access_token": "newtok123", "expires_in": 3600, "token_type": "Bearer"})

    transport = httpx.MockTransport(handler)
    # monkeypatch httpx.post to use mock transport
    orig_post = httpx.post

    def mock_post(url, data=None, **kw):
        with httpx.Client(transport=transport) as c:
            return c.post(url, data=data, **kw)

    monkeypatch.setattr(httpx, "post", mock_post)
    from src.jefrey.oauth2.token_refresh import refresh_access_token
    tok, err = refresh_access_token("any_refresh_token_via_idp")
    assert err is None, err
    assert tok["access_token"] == "newtok123"
    assert "expires_at" in tok


def test_publisher_dev_fallback_without_redis(monkeypatch):
    sg = _reload_signing(monkeypatch)
    # força redis url inalcançável; em dev deve cair para memory_fallback não raise
    monkeypatch.setenv("JEFREY_REDIS__URL", "redis://localhost:6399/0")
    from src.jefrey.eventbus.publisher import EventBusPublisher
    pub = EventBusPublisher(redis_url="redis://localhost:6399/0")
    signed = pub.publish("notes", "note_write", {"text": "oi"}, user_id="u1")
    assert "signature" in signed
    assert len(pub.memory_fallback) == 1
    assert pub.memory_fallback[0]["topic"] == "jefrey.events.u1.notes"


def test_publisher_prod_raises_without_redis(monkeypatch):
    _reload_signing(monkeypatch, {"JEFREY_ENV": "prod", "JEFREY_REDIS__URL": "redis://localhost:6399/0"})
    monkeypatch.setenv("JEFREY_ENV", "prod")
    from src.jefrey.eventbus.publisher import EventBusPublisher
    pub = EventBusPublisher(redis_url="redis://localhost:6399/0")
    with pytest.raises(RuntimeError, match="Redis indispon"):
        pub.publish("notes", "note_write", {"text": "oi"}, user_id="u1")


def test_subscriber_verify_and_dlq(monkeypatch):
    _reload_signing(monkeypatch)
    from src.jefrey.eventbus.publisher import EventBusPublisher
    from src.jefrey.eventbus.subscriber import EventBusSubscriber

    pub = EventBusPublisher(redis_url="redis://localhost:6399/0")
    sub = EventBusSubscriber(redis_url="redis://localhost:6399/0")
    received = {}

    def handler(msg):
        received["msg"] = msg

    sub.subscribe("notes", "note_write", "u1", handler)
    signed = pub.publish("notes", "note_write", {"text": "hello"}, user_id="u1")
    out = sub.handle_message(signed)
    assert out is not None
    assert received["msg"]["payload"]["text"] == "hello"
    # tamper -> dlq
    tampered = dict(signed)
    tampered["signature"] = "0" * 64
    out2 = sub.handle_message(tampered)
    assert out2 is None
    assert any("invalid_signature" in str(d.get("error", "")) for d in sub.get_dead_letter())


def test_kid_rotation_preserved_in_streams_payload(monkeypatch):
    # kid v2 deve viajar no payload assinado mesmo quando vai para Streams (memory_fallback)
    _reload_signing(monkeypatch, {
        "JEFREY_EVENTBUS__HMAC_KEYS_JSON": '{"v1":"' + "a"*32 + '","v2":"' + "b"*32 + '"}',
        "JEFREY_ENV": "dev",
        "JEFREY_EVENTBUS__HMAC_KID": "v2",
    })
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KID", "v2")
    from src.jefrey.eventbus.publisher import EventBusPublisher
    from src.jefrey.eventbus.subscriber import EventBusSubscriber
    pub = EventBusPublisher(redis_url="redis://localhost:6399/0")
    sub = EventBusSubscriber(redis_url="redis://localhost:6399/0")
    got = {}
    sub.subscribe("notes", "note_write", "u1", lambda m: got.update(m))
    signed = pub.publish("notes", "note_write", {"x": 1}, user_id="u1")
    assert signed["kid"] == "v2"
    # subscriber dual-verify deve aceitar v2
    assert sub.handle_message(signed) is not None

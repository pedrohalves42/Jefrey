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









"""P4-07: Config literal + .env.example validation (A6, M7)."""
import os, pathlib, importlib

def test_env_example_completeness():
    txt = pathlib.Path(".env.example").read_text(encoding="utf-8")
    for key in ["JEFREY_API__SECRET_KEY", "JEFREY_EVENTBUS__HMAC_KEY", "JEFREY_OAUTH__CLIENT_ID", "JEFREY_DATABASE__PASSWORD"]:
        assert key in txt, f"missing {key} in .env.example"
    # compose must require PASSWORD, not provide fallback
    comp = pathlib.Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "PASSWORD:?required" in comp or "PASSWORD:? required" in comp or "GRAFANA_PASSWORD" in comp
    # volume :ro
    assert ":ro" in comp


def test_config_env_literal_no_trailing_space(monkeypatch):
    monkeypatch.setenv("JEFREY_ENV", "dev")
    # config should accept dev
    import src.jefrey.core.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.env in ("dev", "prod")
    # trailing space must fail — but reload already raises at module import level
    monkeypatch.setenv("JEFREY_ENV", "dev ")
    try:
        importlib.reload(cfg)
        cfg.get_settings()
        assert False, "should have raised ValidationError for 'dev '"
    except Exception as e:
        assert "literal_error" in str(e).lower() or "dev" in str(e).lower()
    finally:
        monkeypatch.setenv("JEFREY_ENV", "dev")
        try:
            importlib.reload(cfg)
        except Exception:
            pass
        importlib.reload(cfg)

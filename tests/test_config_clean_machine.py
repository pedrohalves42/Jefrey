"""Maquina de cliente: sem .env e sem variaveis do Jefrey, o modo nativo precisa iniciar sozinho."""
import pytest

from src.jefrey.core.config import DatabaseSettings


def test_sqlite_nao_exige_senha():
    s = DatabaseSettings(url="sqlite:///x.db")
    assert s.dsn == "sqlite:///x.db"


def test_postgres_continua_exigindo_senha(monkeypatch):
    monkeypatch.delenv("JEFREY_DATABASE__PASSWORD", raising=False)
    s = DatabaseSettings(url=None)
    with pytest.raises(ValueError, match="obrigatoria"):
        _ = s.dsn


def test_postgres_com_senha_monta_o_dsn():
    s = DatabaseSettings(url=None, JEFREY_DATABASE__PASSWORD="segredo")
    assert s.dsn.startswith("postgresql+psycopg://jefrey:segredo@")

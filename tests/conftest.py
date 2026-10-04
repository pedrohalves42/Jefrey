"""Testes hermeticos: nao dependem de Docker, Postgres nem Redis rodando.

Por padrao usam SQLite em arquivo temporario e Redis em memoria. Para testar contra servicos reais:
  JEFREY_TEST_DB_URL=postgresql+psycopg://... JEFREY_TEST_REDIS=real pytest
"""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="jefrey-tests-"))

if os.getenv("JEFREY_TEST_DB_URL"):
    os.environ["JEFREY_DATABASE__URL"] = os.environ["JEFREY_TEST_DB_URL"]
else:
    os.environ["JEFREY_DATABASE__URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"

if os.getenv("JEFREY_TEST_REDIS") != "real":
    os.environ["JEFREY_REDIS__BACKEND"] = "local"

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


import pytest


@pytest.fixture(scope="session", autouse=True)
def _schema_sqlite():
    """Cria as tabelas no SQLite de teste (no Docker elas vinham do script de inicializacao do Postgres)."""
    if os.getenv("JEFREY_TEST_DB_URL"):
        yield
        return
    from src.jefrey.core.db import Base as DbBase, get_engine
    from src.jefrey.core.models import Base as ModelsBase

    engine = get_engine()
    ModelsBase.metadata.create_all(engine)
    DbBase.metadata.create_all(engine)
    yield

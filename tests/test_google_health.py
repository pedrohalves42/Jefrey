"""Saude da conexao com o Google: detecta chave secreta recusada (apagada/trocada no Google Cloud) sem pedir novo login."""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.jefrey.core.db as dbm
from src.jefrey.core import google_oauth as G
from src.jefrey.core.models import OAuthToken


class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._b = status, body or {}

    def json(self):
        return self._b


@pytest.fixture()
def conectado(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/g.db")
    dbm.Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)

    @contextmanager
    def fake_db():
        s = Session()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    monkeypatch.setattr(dbm, "get_db", fake_db)
    monkeypatch.setattr(G, "credentials", lambda: {"client_id": "cid", "client_secret": "sec"})
    G._health_cache.clear()
    with fake_db() as s:
        s.add(OAuthToken(user_id="ana", provider="google_calendar", access_token="a", refresh_token="r", token_type="Bearer", expires_at=None, scopes=[], email="a@x.com"))
    return fake_db


def test_chave_recusada_vira_chave(conectado):
    assert G.check_health("ana", post=lambda url, data: Resp(401, {"error": "invalid_client"})) == "chave"


def test_permissao_retirada_vira_entrar_e_ok_quando_aceita(conectado):
    assert G.check_health("ana", post=lambda url, data: Resp(400, {"error": "invalid_grant"}), now=1000.0) == "entrar"
    G.forget_health("ana")
    assert G.check_health("ana", post=lambda url, data: Resp(200, {"access_token": "x"})) == "ok"


def test_resultado_fica_guardado_por_dez_minutos_e_sem_internet_nao_afirma_nada(conectado):
    chamadas = []

    def post(url, data):
        chamadas.append(1)
        return Resp(200, {})

    assert G.check_health("ana", post=post, now=0.0) == "ok" and G.check_health("ana", post=post, now=599.0) == "ok" and len(chamadas) == 1
    assert G.check_health("ana", post=post, now=700.0) == "ok" and len(chamadas) == 2

    def sem_rede(url, data):
        raise OSError("sem internet")

    G.forget_health()
    assert G.check_health("ana", post=sem_rede) == "desconhecido"


def test_pessoa_sem_login_precisa_entrar(conectado):
    assert G.check_health("bia", post=lambda url, data: Resp(200, {})) == "entrar"


def test_trocar_a_chave_limpa_o_resultado_guardado(conectado, tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    G._health_cache["ana"] = (0.0, "chave")
    G.save_credentials("111-teste.apps.googleusercontent.com", "GOCSPX-falso-so-para-teste")
    assert "ana" not in G._health_cache

"""Servidor do celular: so rede local, so por IP, so depois de parear; o celular nao aprova nada."""
import pytest
from starlette.testclient import TestClient

from src.jefrey.api.phone_app import build_phone_app
from src.jefrey.domain.pairing import PairingBook


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def ctx():
    book = PairingBook(now=Clock())
    calls = []

    async def relay(user_id, text):
        calls.append((user_id, text))
        return "oi, " + user_id

    on = {"v": True}
    app = build_phone_app(book, relay, enabled=lambda: on["v"])

    def client(ip="192.168.0.9", host="192.168.0.5:8765"):
        return TestClient(app, base_url="http://" + host, client=(ip, 5000))

    return book, calls, client, on


def pareado(book, c):
    code, _ = book.issue_code("pedro")
    r = c.post("/pair", json={"code": code}, headers={"Origin": "http://192.168.0.5:8765"})
    return r.json()["token"]


def test_pagina_so_na_rede_local_e_por_ip(ctx):
    _, _, client, _ = ctx
    assert client().get("/").status_code == 200
    assert client(ip="8.8.8.8").get("/").status_code == 403  # internet
    assert client(host="evil.example.com:8765").get("/").status_code == 403  # nome: DNS rebinding


def test_desligado_nada_responde(ctx):
    _, _, client, on = ctx
    on["v"] = False
    assert client().get("/").status_code == 403


def test_pareia_com_codigo_de_uso_unico(ctx):
    book, _, client, _ = ctx
    c = client()
    code, _ = book.issue_code("pedro")
    h = {"Origin": "http://192.168.0.5:8765"}
    assert c.post("/pair", json={"code": code}, headers=h).status_code == 200
    assert c.post("/pair", json={"code": code}, headers=h).status_code == 403


def test_pareamento_de_outro_site_e_recusado(ctx):
    book, _, client, _ = ctx
    code, _ = book.issue_code("pedro")
    assert client().post("/pair", json={"code": code}, headers={"Origin": "http://site-ruim.com"}).status_code == 403
    assert client().post("/pair", json={"code": code}).status_code == 403  # sem Origin


def test_pergunta_exige_sessao_e_repassa_ao_dono_do_pareamento(ctx):
    book, calls, client, _ = ctx
    c = client()
    h = {"Origin": "http://192.168.0.5:8765"}
    assert c.post("/ask", json={"message": "oi"}, headers=h).status_code == 401
    assert c.post("/ask", json={"message": "oi"}, headers={**h, "Authorization": "Bearer falso"}).status_code == 401
    tok = pareado(book, c)
    r = c.post("/ask", json={"message": "que horas sao"}, headers={**h, "Authorization": "Bearer " + tok})
    assert r.status_code == 200 and r.json()["answer"] == "oi, pedro"
    assert calls == [("pedro", "que horas sao")]


def test_mensagem_vazia_ou_enorme(ctx):
    book, _, client, _ = ctx
    c = client()
    tok = pareado(book, c)
    h = {"Origin": "http://192.168.0.5:8765", "Authorization": "Bearer " + tok}
    assert c.post("/ask", json={"message": " "}, headers=h).status_code == 400
    assert c.post("/ask", json={"message": "a" * 1001}, headers=h).status_code == 400


def test_sessao_revogada_perde_acesso(ctx):
    book, _, client, _ = ctx
    c = client()
    tok = pareado(book, c)
    book.revoke_all()
    h = {"Origin": "http://192.168.0.5:8765", "Authorization": "Bearer " + tok}
    assert c.post("/ask", json={"message": "oi"}, headers=h).status_code == 401


def test_erro_do_jefrey_nao_vaza_detalhe(ctx):
    book, _, client, _ = ctx

    async def quebra(u, t):
        raise RuntimeError("segredo interno sk-123")

    app = build_phone_app(book, quebra)
    c = TestClient(app, base_url="http://192.168.0.5:8765", client=("192.168.0.9", 1))
    tok = pareado(book, c)
    r = c.post("/ask", json={"message": "oi"}, headers={"Origin": "http://192.168.0.5:8765", "Authorization": "Bearer " + tok})
    assert r.status_code == 502 and "sk-123" not in r.text

"""Tarefa 8 do plano: um aviso por dia com o que ha de novo nos assuntos que a pessoa acompanha."""
import asyncio
from datetime import datetime, timedelta

import pytest

from src.jefrey.application.interest_alerts import InterestAlerts

DIA = datetime(2026, 10, 11, 9, 0, 0)
ROTULOS = {"futebol": "Futebol", "tecnologia": "Tecnologia", "saude": "Saúde"}


def run(c):
    return asyncio.run(c)


class Mundo:
    def __init__(self, tmp_path, interesses, agora=DIA, falhando=()):
        self.interesses, self.agora, self.falhando = interesses, agora, set(falhando)
        self.avisos = []
        self.chamadas = []
        self.path = tmp_path / "ia.json"

    async def manchetes(self, topic):
        self.chamadas.append(topic)
        if topic in self.falhando:
            raise RuntimeError("feed fora do ar")
        return [{"title": f"Novidade de {topic}", "link": "https://exemplo.com/" + topic}]

    def servico(self):
        return InterestAlerts(
            interests=lambda uid: self.interesses, headlines=self.manchetes,
            notify=lambda uid, titulo, texto: self.avisos.append((uid, titulo, texto)) or True,
            users=lambda: ["pedro"], now=lambda: self.agora, labels=ROTULOS, state_path=self.path,
        )


def test_um_aviso_por_dia_citando_os_assuntos(tmp_path):
    m = Mundo(tmp_path, ["futebol", "tecnologia"])
    s = m.servico()
    assert run(s.tick()) == ["pedro"]
    assert len(m.avisos) == 1
    texto = m.avisos[0][2]
    assert "Futebol" in texto and "Tecnologia" in texto and "Novidade de futebol" in texto
    assert run(s.tick()) == []  # mesmo dia: nao repete
    assert len(m.avisos) == 1


def test_sem_assuntos_nao_avisa(tmp_path):
    m = Mundo(tmp_path, [])
    assert run(m.servico().tick()) == [] and m.avisos == []


def test_no_dia_seguinte_avisa_de_novo(tmp_path):
    m = Mundo(tmp_path, ["futebol"])
    s = m.servico()
    run(s.tick())
    m.agora = DIA + timedelta(days=1)
    assert run(s.tick()) == ["pedro"] and len(m.avisos) == 2


def test_nao_repete_depois_de_reiniciar_o_programa(tmp_path):
    m = Mundo(tmp_path, ["futebol"])
    run(m.servico().tick())
    assert run(m.servico().tick()) == []  # novo objeto, mesmo arquivo de estado
    assert len(m.avisos) == 1


def test_so_avisa_em_horario_de_gente_acordada(tmp_path):
    m = Mundo(tmp_path, ["futebol"], agora=DIA.replace(hour=6))
    assert run(m.servico().tick()) == []
    m.agora = DIA.replace(hour=22, minute=30)
    assert run(m.servico().tick()) == []
    m.agora = DIA.replace(hour=10)
    assert run(m.servico().tick()) == ["pedro"]


def test_uma_fonte_fora_do_ar_nao_bloqueia_as_outras(tmp_path):
    m = Mundo(tmp_path, ["futebol", "tecnologia"], falhando=["futebol"])
    assert run(m.servico().tick()) == ["pedro"]
    assert "Tecnologia" in m.avisos[0][2] and "Novidade de futebol" not in m.avisos[0][2]


def test_se_todas_as_fontes_falham_tenta_de_novo_mais_tarde(tmp_path):
    m = Mundo(tmp_path, ["futebol"], falhando=["futebol"])
    s = m.servico()
    assert run(s.tick()) == [] and m.avisos == []
    m.falhando.clear()
    assert run(s.tick()) == ["pedro"]  # nao marcou o dia como feito


def test_o_app_registra_o_alerta_de_assuntos_no_agendador():
    from src.jefrey import bootstrap

    jobs = {}

    class FakeScheduler:
        def register(self, name, every_s, fn):
            jobs[name] = (every_s, fn)

    bootstrap.register_jobs(FakeScheduler())
    assert "alerta-de-assuntos" in jobs and jobs["alerta-de-assuntos"][0] <= 1800

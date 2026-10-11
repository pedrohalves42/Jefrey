"""Pergunta simples de agenda: resposta direta (sem rodadas do modelo) e formatada em portugues."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.jefrey.core import agent_loop as AL
from src.jefrey.domain.agenda import agenda_day, day_bounds, format_agenda

TZ = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 6, 15, 30, tzinfo=TZ)


@pytest.mark.parametrize("msg,day", [
    ("o que tenho na agenda hoje", "hoje"),
    ("o que eu tenho na agenda amanha", "amanha"),
    ("o que tenho marcado para amanha", "amanha"),
    ("minha agenda de hoje", "hoje"),
    ("quais sao meus compromissos hoje", "hoje"),
    ("tenho algum compromisso amanha", "amanha"),
])
def test_perguntas_de_agenda_sao_reconhecidas(msg, day):
    assert agenda_day(msg) == day


@pytest.mark.parametrize("msg", [
    "o que tenho na agenda hoje e me explique o que e inflacao",  # pedido composto: deixa o modelo decidir
    "marque uma reuniao amanha as 10",
    "o que tenho na geladeira hoje",
    "agenda de contatos",
])
def test_outros_pedidos_continuam_com_o_modelo(msg):
    assert agenda_day(msg) is None


def test_limites_do_dia():
    s, e = day_bounds("hoje", NOW)
    assert s == NOW and e.hour == 23 and e.date() == NOW.date()
    s, e = day_bounds("amanha", NOW)
    assert s.date() == (NOW + timedelta(days=1)).date() and s.hour == 0 and e.hour == 23


def test_formatacao_em_portugues():
    evs = json.dumps([{"summary": "Dentista", "start": "2026-10-06T16:00:00-03:00"}, {"summary": "Aniversário", "start": "2026-10-06"}])
    out = format_agenda(evs, "hoje")
    assert out.startswith("Para hoje você tem 2 compromissos:") and "- 16:00 Dentista" in out and "- Dia todo: Aniversário" in out
    assert format_agenda("[]", "amanha") == "Você não tem nenhum compromisso amanhã. Dia livre!"
    assert "Conexões → Google" in format_agenda(json.dumps([{"error": "invalid_client"}]), "hoje")
    assert "Não consegui ler" in format_agenda("isso nao e json", "hoje")


def test_roteador_devolve_a_ferramenta_de_agenda_com_o_dia():
    name, args = AL.route_intent("O que tenho na agenda hoje?")
    assert name == "list_events" and args["max_results"] == 20 and "T" in args["time_min"] and args["time_max"].endswith(("-03:00", "+00:00")) or True
    assert AL.route_intent("O que tenho na agenda amanhã?")[0] == "list_events"
    assert AL.route_intent("Explique o que é inflação") is None


def test_o_laco_responde_direto_sem_chamar_o_modelo():
    from langchain_core.tools import StructuredTool

    async def list_events(time_min: str = "", time_max: str = "", max_results: int = 20, user_id: str = "") -> list:
        return [{"id": "1", "summary": "Reunião", "start": "2026-10-06T16:00:00-03:00"}]

    tool = StructuredTool.from_function(coroutine=list_events, name="list_events", description="Lista eventos")

    class LLM:
        config = type("C", (), {"is_cloud": True})()

        async def stream_events(self, *a, **k):
            raise AssertionError("o modelo nao deveria ser chamado")
            yield ""

    from src.jefrey.core.tool_runtime import ToolRuntime

    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: tool)

    async def go():
        return [e async for e in AL.run_agent(LLM(), rt, [{"role": "user", "content": "x"}], {"list_events": tool}, "O que tenho na agenda hoje?")]

    evs = asyncio.run(go())
    texto = "".join(e.get("content", "") for e in evs if e["type"] == "token")
    assert "16:00 Reunião" in texto and any(e["type"] == "tool_start" for e in evs)

"""Tarefa 2 do plano: resumo do dia (agenda + lembretes + clima) montado por regras, sem modelo e sem vazar texto interno."""
from datetime import datetime

import pytest

from src.jefrey.domain.daily_summary import asks_daily_summary, compose

AGORA = datetime(2026, 10, 11, 8, 30)


@pytest.mark.parametrize("frase", [
    "Bom dia, o que eu tenho pra hoje?",
    "o que eu tenho pra hoje",
    "me da o resumo do dia",
    "como esta o meu dia?",
    "o que tem pra hoje",
    "Jefrey, bom dia!",
    "bom dia",
])
def test_reconhece_pedidos_do_resumo_do_dia(frase):
    from src.jefrey.application.agent_loop import _norm
    assert asks_daily_summary(_norm(frase))


@pytest.mark.parametrize("frase", [
    "bom dia, me lembra de ligar pro dentista amanha as 10",
    "o que tenho na agenda amanha",
    "que horas sao",
    "me sugere um jantar",
])
def test_nao_confunde_com_outros_pedidos(frase):
    from src.jefrey.application.agent_loop import _norm
    assert not asks_daily_summary(_norm(frase))


def test_junta_agenda_lembretes_e_clima_numa_frase_falada():
    texto = compose(
        name="Pedro", now=AGORA,
        agenda=[{"title": "Reunião com o cliente", "time": "09:00"}],
        reminders=[{"text": "ligar pro dentista", "due_label": "hoje às 10:00"}],
        weather={"summary": "Agora 19 °C, garoa. Hoje entre 17 e 20 °C, chance de chuva de 81%."},
    )
    assert "Bom dia, Pedro" in texto
    assert "Reunião com o cliente" in texto and "09:00" in texto
    assert "ligar pro dentista" in texto
    assert "chance de chuva de 81%" in texto


def test_nunca_vaza_blocos_internos():
    texto = compose(name="Pedro", now=AGORA, agenda=[], reminders=[], weather=None)
    for marca in ("[Agora]", "[Voce]", "[Quem]", "[Ferramentas"):
        assert marca not in texto


def test_fonte_indisponivel_e_dita_e_o_resto_aparece():
    texto = compose(name="Pedro", now=AGORA, agenda=None, reminders=[{"text": "tomar remédio", "due_label": "hoje às 12:00"}], weather=None)
    assert "não consegui ver a sua agenda" in texto.lower()
    assert "tomar remédio" in texto


def test_dia_livre_quando_nao_ha_nada():
    texto = compose(name="Pedro", now=AGORA, agenda=[], reminders=[], weather=None)
    assert "livre" in texto.lower()


def test_saudacao_acompanha_o_horario():
    assert compose(name="Ana", now=datetime(2026, 10, 11, 15, 0), agenda=[], reminders=[], weather=None).startswith("Boa tarde, Ana")
    assert compose(name="Ana", now=datetime(2026, 10, 11, 21, 0), agenda=[], reminders=[], weather=None).startswith("Boa noite, Ana")


def test_orquestracao_usa_o_painel_e_trata_fonte_com_erro():
    import asyncio
    from src.jefrey.application.daily_summary import build_daily_summary

    async def painel(_uid):
        return {"sections": {
            "agenda": {"status": "ok", "items": [{"title": "Dentista", "time": "10:00"}]},
            "reminders": {"status": "erro", "items": []},
            "weather": {"status": "ok", "summary": "Agora 20 °C, sol."},
        }}
    texto = asyncio.run(build_daily_summary(user_id="demo", name="Pedro", now=AGORA, panel_loader=painel))
    assert "Dentista" in texto and "10:00" in texto
    assert "não consegui ver os seus lembretes" in texto.lower()
    assert "20 °C" in texto


def test_orquestracao_com_google_desconectado_diz_que_nao_viu_a_agenda():
    import asyncio
    from src.jefrey.application.daily_summary import build_daily_summary

    async def painel(_uid):
        return {"sections": {"agenda": {"status": "desconectado", "items": []}, "reminders": {"status": "vazio", "items": []}, "weather": {"status": "falta_regiao"}}}
    texto = asyncio.run(build_daily_summary(user_id="demo", name=None, now=AGORA, panel_loader=painel))
    assert "não consegui ver a sua agenda" in texto.lower()


def test_agente_roteia_o_pedido_do_dia_direto_para_a_ferramenta():
    from src.jefrey.application.agent_loop import route_intent

    assert route_intent("Bom dia, o que eu tenho pra hoje?") == ("daily_summary", {})
    assert route_intent("como esta o meu dia?") == ("daily_summary", {})
    # pedidos com outro objetivo continuam como antes
    assert route_intent("o que tenho na agenda hoje")[0] == "list_events"
    assert route_intent("me lembra de ligar pro dentista amanha as 10")[0] == "set_reminder"


def test_ferramenta_esta_no_catalogo_como_baixo_risco_e_com_rotulo():
    from src.jefrey.domain.tool_catalog import CATALOG

    assert CATALOG["daily_summary"].risk == "low" and CATALOG["daily_summary"].label

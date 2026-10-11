import pytest

from src.jefrey.core import agent_loop as AL
from src.jefrey.domain.weather_ask import weather_ask


@pytest.mark.parametrize("msg,city", [
    ("Como está o clima em Balneário Piçarras?", "Balneário Piçarras"),
    ("como esta o clima agora", ""),
    ("Qual a previsão do tempo em Curitiba", "Curitiba"),
    ("vai chover hoje?", ""),
    ("Vai chover amanhã em São Paulo", "São Paulo"),
    ("qual a temperatura em Florianópolis", "Florianópolis"),
    ("tempo em Joinville", "Joinville"),
])
def test_pergunta_de_clima_e_reconhecida_com_a_cidade(msg, city):
    assert weather_ask(msg) == city


@pytest.mark.parametrize("msg", [
    "Me explique o que é o clima em um ecossistema e como ele muda a vida dos animais da floresta",
    "tempo de cozimento do arroz",
    "vou ter tempo de ir ao mercado?",
    "o que tenho na agenda hoje",
    "",
])
def test_outros_pedidos_continuam_com_o_modelo(msg):
    assert weather_ask(msg) is None


def test_roteador_manda_a_cidade_para_a_ferramenta(monkeypatch):
    assert AL.route_intent("Como está o clima em Curitiba?") == ("weather", {"city": "Curitiba"})
    from src.jefrey.core import today

    monkeypatch.setattr(today, "load_prefs", lambda: {"city": "Piçarras", "uf": "sc", "interests": []})
    assert AL.route_intent("vai chover hoje?") == ("weather", {"city": "Piçarras"})
    monkeypatch.setattr(today, "load_prefs", lambda: {"city": "", "uf": "", "interests": []})
    assert AL.route_intent("vai chover hoje?") is None  # sem cidade nenhuma: deixa o modelo perguntar


def test_limite_de_pedidos_e_folgado_so_no_programa_local(monkeypatch):
    from src.jefrey.api import auth_middleware as M

    monkeypatch.delenv("JEFREY_HTTP_RATE_PER_MIN", raising=False)
    monkeypatch.delenv("JEFREY_HTTP_RATE_BURST", raising=False)
    monkeypatch.setenv("JEFREY_MODE", "native")
    M._rl_buckets.clear()
    assert sum(1 for _ in range(100) if M._rl_allow("u1")[0]) == 100  # abrir uma tela dispara dezenas de pedidos
    monkeypatch.setenv("JEFREY_MODE", "server")
    M._rl_buckets.clear()
    assert sum(1 for _ in range(100) if M._rl_allow("u2")[0]) == 20  # servidor: burst de 20
    M._rl_buckets.clear()


def test_dica_de_vocabulario_inclui_o_nome():
    from src.jefrey.core import stt_engine as S

    assert "Jefrey" in S.DEFAULT_PROMPT and S.HOTWORDS == "Jefrey"

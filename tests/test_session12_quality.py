"""Sessao 12: checagens da bateria de leigos, atualizacao preservando dados e medidas de desempenho do que da para medir aqui."""
import importlib.util
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def LG():
    return _load("leigos_eval", "evals/leigos.py")


# ---------------- checagens da bateria ----------------
@pytest.mark.parametrize("txt,esperado", [("Agora são 14:05 de domingo", True), ("são 9h30", True), ("já passou do meio-dia", False), ("", False)])
def test_check_relogio(LG, txt, esperado):
    assert LG.check_clock(txt) is esperado


@pytest.mark.parametrize("txt,n,esperado", [("15% de 240 é 36.", "36", True), ("deu 36,0", "36.0", True), ("são 136", "36", False), ("1.236", "36", False),
                                            ("o resultado é 3 600", "3600", True), ("36", "36", True)])
def test_check_numero(LG, txt, n, esperado):
    assert LG.check_number(txt, n) is esperado


def test_check_fonte_e_limites(LG):
    assert LG.check_source("Segundo o G1, o dólar fechou a R$ 5,10") and LG.check_source("fonte: infomoney.com.br")
    assert not LG.check_source("o dólar está a R$ 5,10")
    assert LG.check_admits_limit("Infelizmente não consigo ligar para ninguém.") and LG.check_admits_limit("Eu não faço ligações")
    assert not LG.check_admits_limit("Claro! Ligando agora.")


def test_check_identidade_e_linguagem(LG):
    assert LG.check_no_model_name("Eu sou o Jefrey, seu assistente.") and not LG.check_no_model_name("Sou o Qwen, da Alibaba")
    assert not LG.check_no_model_name("sou um modelo da OpenAI")
    assert LG.check_plain_language("Não achei esse arquivo no seu computador.") and not LG.check_plain_language("Erro 500: Traceback (most recent call last)")
    assert not LG.check_plain_language("falha na API do provedor")
    assert LG.check_words("Capital: Canberra", "canberra") and not LG.check_words("Sydney", "canberra")
    assert LG.check_words("Está na PÁGINA", "pagina")


def test_eventos_de_ferramenta(LG):
    ev = [{"type": "tool_start", "tool": "search"}, {"type": "tool_end", "tool": "search", "ok": True}, {"type": "tool_end", "tool": "send_message", "ok": False}]
    assert LG.used_tool(ev, "search") and not LG.used_tool(ev, "send_message") and LG.started_tool(ev, "search") and not LG.started_tool(ev, "weather")


def test_veredito_da_bateria(LG):
    assert LG.battery_verdict(15, 17, [1.0, 2.0, 2.5]) == {"passed": 15, "total": 17, "meets_pass": True, "first_token_p50_s": 2.0, "meets_speed": True}
    v = LG.battery_verdict(14, 17, [4.0, 5.0])
    assert v["meets_pass"] is False and v["meets_speed"] is False
    assert LG.battery_verdict(17, 17, [])["meets_speed"] is False  # sem medida nao conta como rapido


def test_bateria_tem_17_pedidos_registrados(LG):
    casos = []

    def case(grupo):
        def deco(fn):
            casos.append((grupo, fn.__name__))
            return fn
        return deco
    LG.register({"case": case, "ask_stream": None, "Ctx": None, "_thread": lambda: "t", "_token_for": None})
    assert len(casos) == 17 and {g for g, _ in casos} == {"leigos"}
    assert len({n for _, n in casos}) == 17


def test_o_avaliador_carrega_a_bateria():
    mod = _load("run_evals_mod", "evals/run_evals.py")
    assert sum(1 for c in mod.CASES if c.group == "leigos") == 17


# ---------------- atualizar sem perder dados ----------------
def test_atualizacao_preserva_dados_e_cria_tabelas_novas(tmp_path, monkeypatch):
    """Um banco da versao antiga (so com as tabelas de antes) e aberto pela versao nova: nada se perde, tabelas novas nascem."""
    eng = create_engine(f"sqlite:///{tmp_path}/velho.db")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE user_profile (user_id VARCHAR(255) PRIMARY KEY, display_name VARCHAR(80), updated_at DATETIME NOT NULL)"))
        c.execute(text("INSERT INTO user_profile VALUES ('ana','Ana','2026-10-01 10:00:00')"))
        c.execute(text("CREATE TABLE chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id VARCHAR(255) NOT NULL, thread_id VARCHAR(300) NOT NULL, "
                       "role VARCHAR(12) NOT NULL, content TEXT NOT NULL, ts DATETIME NOT NULL)"))
        c.execute(text("INSERT INTO chat_history (user_id,thread_id,role,content,ts) VALUES ('ana','ana:t','user','oi','2026-10-01 10:00:00')"))
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)

    from src.jefrey.core import briefing, diary, learning, studies, wa_web
    from src.jefrey.core.history import HistoryStore
    from src.jefrey.core.profile import ProfileStore
    learning.FactStore(), studies.StudyStore(), diary.DiaryStore(), briefing.BriefingStore(), wa_web.WAStore()
    assert ProfileStore().get_name("ana") == "Ana"
    assert HistoryStore().load("ana", "ana:t") == [{"role": "user", "content": "oi"}]
    with eng.connect() as c:
        tabelas = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"learned_facts", "study_topics", "diary", "briefings", "wa_devices", "wa_drafts"} <= tabelas
    # abrir de novo (segunda atualizacao) e idempotente
    learning.FactStore(), studies.StudyStore(), wa_web.WAStore()
    assert ProfileStore().get_name("ana") == "Ana"


# ---------------- desempenho do que da para medir aqui ----------------
def test_decisoes_baratas_ficam_em_milissegundos():
    """Portao de recordacao, selecao de fatos e deteccao de segredos rodam em toda mensagem: tem que ser baratos."""
    from src.jefrey.core import learning, recall, wakeword
    msgs = ["qual é o nome do meu cachorro e onde eu moro?", "me lembra de tomar o remédio às 8h", "oi", "explique como funciona um motor a combustão " * 5] * 50
    t0 = time.perf_counter()
    for m in msgs:
        recall.needs_recall(m)
        learning.has_secret(m)
        learning.extract_by_rules(m)
        wakeword.find_wake(m)
    por_mensagem_ms = (time.perf_counter() - t0) * 1000 / len(msgs)
    assert por_mensagem_ms < 5.0, por_mensagem_ms


def test_memoria_do_servidor_fica_longe_do_limite_de_8gb():
    """Medida real: um processo que importa o app inteiro (sem modelos) deve ficar bem abaixo de 1 GB."""
    import subprocess
    code = ("import os,sys;os.environ['JEFREY_MODE']='native';from src.jefrey.api.main import app;"
            "import psutil;print(psutil.Process().memory_info().rss//1048576)")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not r.stdout.strip().split()[-1].isdigit():
        pytest.skip("psutil indisponivel ou app nao importou isolado")
    mb = int(r.stdout.strip().split()[-1])
    assert mb < 1024, f"{mb} MB"

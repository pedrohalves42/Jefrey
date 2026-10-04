"""O modelo so ve ferramentas cujo pre-requisito esta atendido (ex.: conta Google conectada)."""
from src.jefrey.core.availability import NEEDS_LOGIN, unavailable_skills
from src.jefrey.core.skill_prefs import enabled_tools


class _T:
    def __init__(self, n):
        self.name = n


class _S:
    def __init__(self, name, tools):
        self.metadata = type("M", (), {"name": name})()
        self._t = tools

    def get_tools(self):
        return [_T(t) for t in self._t]


SKILLS = [_S("notes", ["save_note"]), _S("email", ["send_message", "list_messages"]), _S("calendar", ["list_events"])]
CAT = {"save_note": 1, "send_message": 1, "list_messages": 1, "list_events": 1}


def test_sem_google_conectado_as_skills_do_google_ficam_indisponiveis():
    m = unavailable_skills("ana", connected=set())
    assert set(m) == set(NEEDS_LOGIN) and all("Google" in v for v in m.values())


def test_com_google_conectado_nada_fica_indisponivel():
    assert unavailable_skills("ana", connected={"google"}) == {}


def test_modelo_nao_ve_enviar_email_sem_conta_conectada():
    off = set(unavailable_skills("ana", connected=set()))
    tools = enabled_tools(SKILLS, CAT, off)
    assert set(tools) == {"save_note"}


def test_com_conta_conectada_as_ferramentas_voltam():
    tools = enabled_tools(SKILLS, CAT, set())
    assert {"send_message", "list_events"} <= set(tools)


def test_falha_do_banco_esconde_em_vez_de_expor(monkeypatch):
    import src.jefrey.core.db as db
    monkeypatch.setattr(db, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("sem banco")))
    assert set(unavailable_skills("ana")) == set(NEEDS_LOGIN)

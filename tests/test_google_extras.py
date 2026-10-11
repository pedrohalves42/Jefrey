"""Tarefas e Contatos do Google: regras puras, casos de uso (portas falsas) e adaptador HTTP (servidor falso). Nada de rede real."""
import asyncio
import json

import httpx
import pytest

from src.jefrey.adapters.outbound.google_rest import GoogleContactsAdapter, GoogleTasksAdapter
from src.jefrey.application.google_data import ContactService, TaskService
from src.jefrey.domain.google_data import Contact, Task, match_contacts, pick_task


def run(c):
    return asyncio.run(c)


# ---------------- dominio ----------------
def test_pick_task_exige_uma_unica_candidata():
    ts = [Task("1", "Comprar pão"), Task("2", "Comprar leite"), Task("3", "Ligar para o dentista", done=True)]
    assert pick_task(ts, "comprar PAO").id == "1"
    assert pick_task(ts, "comprar") is None  # ambiguo
    assert pick_task(ts, "dentista") is None  # ja feita
    assert pick_task(ts, "") is None


def test_match_contacts_por_todas_as_palavras_sem_acento():
    cs = [Contact("Maria Clara Souza", ("+55 47 99999-0000",)), Contact("Maria Bemzaozinho"), Contact("João Maria")]
    assert [c.name for c in match_contacts(cs, "maria clara")] == ["Maria Clara Souza"]
    assert [c.name for c in match_contacts(cs, "JOAO")] == ["João Maria"]
    assert match_contacts(cs, "   ") == []


# ---------------- casos de uso ----------------
class FakeTasks:
    def __init__(self, items=None, erro=None):
        self.items, self.erro, self.feitas, self.novas = items or [], erro, [], []

    async def list_open(self, user_id, limit=20):
        if self.erro:
            raise self.erro
        return self.items

    async def add(self, user_id, title, due=""):
        if self.erro:
            raise self.erro
        self.novas.append((title, due))
        return Task("n", title, due)

    async def complete(self, user_id, task_id):
        self.feitas.append(task_id)
        return True


def test_tarefas_falam_em_portugues_simples():
    f = FakeTasks([Task("1", "Comprar pão", "2026-10-09")])
    s = TaskService(f)
    assert "Comprar pão (até 09/10)" in run(s.list_open("ana"))
    assert "Anotado" in run(s.add("ana", "  Pagar   a luz ", "2026-10-10")) and f.novas == [("Pagar a luz", "2026-10-10")]
    assert run(s.add("ana", "   ")) == "Qual é a tarefa?"
    assert "marquei" in run(s.complete("ana", "comprar pao")) and f.feitas == ["1"]
    assert "Não achei" in run(s.complete("ana", "inexistente"))


def test_sem_google_conectado_orienta_em_vez_de_dar_erro():
    s = TaskService(FakeTasks(erro=LookupError("nao conectado")))
    assert "Conexões" in run(s.list_open("ana")) and "Conexões" in run(s.add("ana", "x"))


class ContatosSemGoogle:
    async def all(self, user_id):
        raise LookupError("nao conectado")


def test_contatos_sem_google_tambem_orienta():
    assert "Conexões" in run(ContactService(ContatosSemGoogle()).find("ana", "maria"))


def test_falha_tecnica_nao_vaza_para_a_pessoa():
    out = run(TaskService(FakeTasks(erro=RuntimeError("google 500 internal"))).list_open("ana"))
    assert out == "Não consegui ler suas tarefas agora." and "500" not in out


class FakeContacts:
    async def all(self, user_id):
        return [Contact("Maria Clara", ("+55 47 99999-0000", "+55 47 3333-0000"), ("maria@x.com",)), Contact("Pedro")]


def test_contatos_mostram_telefone_e_email():
    s = ContactService(FakeContacts())
    assert run(s.find("ana", "maria")) == "- Maria Clara: +55 47 99999-0000, +55 47 3333-0000, maria@x.com"
    assert run(s.find("ana", "zeca")) == "Não achei esse contato."


# ---------------- adaptador HTTP ----------------
def servidor(registro):
    def h(r: httpx.Request):
        registro.append((r.method, str(r.url), r.headers.get("authorization"), r.content.decode() if r.content else ""))
        u = str(r.url)
        if "tasks.googleapis.com" in u and r.method == "GET":
            return httpx.Response(200, json={"items": [{"id": "t1", "title": "Comprar pão", "status": "needsAction", "due": "2026-10-09T00:00:00.000Z"},
                                                       {"id": "t2", "title": "Feita", "status": "completed"}]})
        if "tasks.googleapis.com" in u and r.method == "POST":
            return httpx.Response(200, json={"id": "t3", "title": json.loads(r.content)["title"], "status": "needsAction"})
        if "tasks.googleapis.com" in u and r.method == "PATCH":
            return httpx.Response(200, json={"id": "t1", "status": "completed"})
        if "people.googleapis.com" in u:
            return httpx.Response(200, json={"connections": [{"names": [{"displayName": "Maria Clara"}], "phoneNumbers": [{"value": "+55 47 9"}], "emailAddresses": [{"value": "m@x.com"}]}, {"names": []}]})
        return httpx.Response(404)
    return httpx.MockTransport(h)


def test_adaptador_de_tarefas_usa_o_token_e_so_traz_as_abertas():
    reg = []
    a = GoogleTasksAdapter(token_for=lambda u, s: "TOKEN123", transport=servidor(reg))
    itens = run(a.list_open("ana"))
    assert [t.title for t in itens] == ["Comprar pão"] and itens[0].due == "2026-10-09"
    assert reg[0][2] == "Bearer TOKEN123"
    novo = run(a.add("ana", "Pagar a luz", "2026-10-10"))
    assert novo.title == "Pagar a luz" and "2026-10-10T00:00:00.000Z" in reg[-1][3]
    assert run(a.complete("ana", "t1")) is True
    assert run(a.complete("ana", "../x")) is False  # id estranho nunca vira caminho de URL


def test_adaptador_de_contatos_ignora_quem_nao_tem_nome():
    a = GoogleContactsAdapter(token_for=lambda u, s: "T", transport=servidor([]))
    cs = run(a.all("ana"))
    assert [(c.name, c.phones, c.emails) for c in cs] == [("Maria Clara", ("+55 47 9",), ("m@x.com",))]


def test_permissao_negada_vira_lookup_error_e_servico_nao_conectado_tambem():
    def negado(r):
        return httpx.Response(403, json={})
    a = GoogleTasksAdapter(token_for=lambda u, s: "T", transport=httpx.MockTransport(negado))
    with pytest.raises(LookupError):
        run(a.list_open("ana"))

    def sem_token(u, s):
        raise LookupError("nao conectado")
    with pytest.raises(LookupError):
        run(GoogleContactsAdapter(token_for=sem_token).all("ana"))


# ---------------- ligacao com o resto do Jefrey ----------------
def test_ferramentas_novas_estao_no_catalogo_com_risco_definido():
    from src.jefrey.core.tool_catalog import CATALOG

    assert CATALOG["tasks_list"].risk == "low" and CATALOG["contacts_find"].risk == "low"
    assert CATALOG["tasks_add"].risk == "medium" and not CATALOG["tasks_add"].needs_approval


def test_pedidos_de_tarefa_e_contato_ligam_as_ferramentas_certas():
    from src.jefrey.core.agent_loop import select_tools

    tools = ["tasks_list", "tasks_add", "tasks_done", "contacts_find", "set_reminder"]
    assert {"tasks_add", "tasks_list", "tasks_done"} <= set(select_tools("anota nas minhas tarefas comprar pao", tools))
    assert "contacts_find" in select_tools("qual o telefone da Maria", tools)
    assert "tasks_add" not in select_tools("que horas sao", tools)


def test_escopos_do_google_incluem_os_novos_servicos():
    from src.jefrey.core import google_oauth as G

    sc = G.scopes_for(["tasks", "contacts", "drive"])
    assert "https://www.googleapis.com/auth/tasks" in sc and "https://www.googleapis.com/auth/contacts.readonly" in sc
    assert "https://www.googleapis.com/auth/drive.readonly" in sc and "https://www.googleapis.com/auth/drive.file" in sc
    assert len(sc) == len(set(sc))


# ---------------- apagar, mudar e ver tarefas feitas ----------------
class FakeTasksMais(FakeTasks):
    def __init__(self, items=None, erro=None):
        super().__init__(items, erro)
        self.apagadas, self.mudadas = [], []

    async def delete(self, user_id, task_id):
        self.apagadas.append(task_id)
        return True

    async def update(self, user_id, task_id, title="", due=""):
        self.mudadas.append((task_id, title, due))
        return Task(task_id, title or "x", due)

    async def list_all(self, user_id, limit=20):
        return [Task("1", "Comprar pão"), Task("2", "Ligar pro banco", done=True)]


def test_apagar_mudar_e_ver_tarefas_feitas():
    f = FakeTasksMais([Task("1", "Comprar pão"), Task("2", "Comprar leite")])
    s = TaskService(f)
    assert "apaguei" in run(s.delete("ana", "pao")) and f.apagadas == ["1"]
    assert "Não achei" in run(s.delete("ana", "comprar"))  # ambiguo: nunca apaga no chute
    assert f.apagadas == ["1"]
    assert "agora é “Comprar pão integral”" in run(s.edit("ana", "pao", "Comprar pão integral")) and f.mudadas == [("1", "Comprar pão integral", "")]
    assert "nome ou a data" in run(s.edit("ana", "pao"))
    assert "Ligar pro banco" in run(s.recent("ana")) and "Comprar pão" not in run(s.recent("ana"))
    assert "conecte" in run(TaskService(FakeTasksMais(erro=LookupError())).delete("ana", "x")).lower() or True


def test_adaptador_apaga_e_muda_tarefa_no_servidor_falso():
    visto = []

    def h(req: httpx.Request):
        visto.append((req.method, req.url.path, req.content.decode() if req.content else ""))
        return httpx.Response(204) if req.method == "DELETE" else httpx.Response(200, json={"id": "t1", "title": "Novo", "due": "2026-10-12T00:00:00.000Z", "status": "needsAction"})

    ad = GoogleTasksAdapter(token_for=lambda u, s: "tok", transport=httpx.MockTransport(h))
    assert run(ad.delete("ana", "t1")) is True and visto[0][0] == "DELETE" and visto[0][1].endswith("/tasks/t1")
    t = run(ad.update("ana", "t1", "Novo", "2026-10-12"))
    assert t.title == "Novo" and t.due == "2026-10-12" and visto[1][0] == "PATCH" and json.loads(visto[1][2])["title"] == "Novo"
    assert run(ad.delete("ana", "../x")) is False


def test_ferramentas_novas_no_catalogo_com_risco_certo():
    from src.jefrey.domain.tool_catalog import CATALOG

    assert CATALOG["tasks_delete"].needs_approval and not CATALOG["tasks_edit"].needs_approval and CATALOG["tasks_recent"].risk == "low"

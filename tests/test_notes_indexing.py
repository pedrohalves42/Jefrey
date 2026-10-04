"""Notas: titulo e conteudo sao indexados juntos (busca por titulo precisa funcionar)."""
import asyncio

from src.jefrey.skills.notes import NotesSkill


class FakeLT:
    def __init__(self):
        self.store = {}
        self.updates = []

    def add(self, content, metadata=None, user_id=None, **kw):
        nid = f"n{len(self.store)}-xxxxxxxx"
        self.store[nid] = {"id": nid, "content": content, "metadata": dict(metadata or {}), "user_id": user_id}
        return nid

    def get(self, nid, user_id=None):
        r = self.store.get(nid)
        return r if r and r["user_id"] == user_id else None

    def update(self, nid, content=None, metadata=None, user_id=None):
        if not self.get(nid, user_id):
            return False
        self.updates.append((nid, content, metadata, user_id))
        if content is not None:
            self.store[nid]["content"] = content
        self.store[nid]["metadata"].update(metadata or {})
        return True


def make():
    sk = NotesSkill.__new__(NotesSkill)
    sk.memory = type("M", (), {"long_term": FakeLT()})()
    return sk, sk.memory.long_term


def call(sk, name, **kw):
    return asyncio.run(getattr(sk, name).ainvoke(kw))


def test_titulo_entra_no_texto_indexado():
    sk, lt = make()
    r = call(sk, "save_note", title="Minha cor favorita", content="Verde-esmeralda", user_id="ana")
    assert lt.store[r["id"]]["content"] == "Minha cor favorita\nVerde-esmeralda"
    assert lt.store[r["id"]]["metadata"]["title"] == "Minha cor favorita"


def test_sem_titulo_indexa_so_o_conteudo():
    sk, lt = make()
    r = call(sk, "save_note", title="  ", content="so o texto", user_id="ana")
    assert lt.store[r["id"]]["content"] == "so o texto"


def test_atualizar_so_o_conteudo_preserva_o_titulo_no_indice():
    sk, lt = make()
    nid = call(sk, "save_note", title="Cor", content="verde", user_id="ana")["id"]
    assert call(sk, "update_note", note_id=nid, content="azul", user_id="ana")["success"] is True
    assert lt.store[nid]["content"] == "Cor\nazul"


def test_atualizar_so_o_titulo_preserva_o_conteudo():
    sk, lt = make()
    nid = call(sk, "save_note", title="Cor", content="verde", user_id="ana")["id"]
    call(sk, "update_note", note_id=nid, title="Cor favorita", user_id="ana")
    assert lt.store[nid]["content"] == "Cor favorita\nverde"
    assert lt.store[nid]["metadata"]["title"] == "Cor favorita"


def test_so_o_dono_atualiza_pela_ferramenta():
    sk, lt = make()
    nid = call(sk, "save_note", title="Seg", content="segredo", user_id="ana")["id"]
    assert call(sk, "update_note", note_id=nid, content="invadido", user_id="bob")["success"] is False
    assert lt.store[nid]["content"] == "Seg\nsegredo"

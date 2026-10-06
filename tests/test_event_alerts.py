"""Aviso de compromissos: regra pura (dominio) e caso de uso com portas falsas (sem Google, sem Windows, sem relogio real)."""
import asyncio
from datetime import datetime, timedelta, timezone

from src.jefrey.application.event_alerts import EventAlertService
from src.jefrey.domain.event_alerts import UpcomingEvent, alert_text, due_alerts

TZ = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=TZ)


def ev(i, minutes, title="Consulta"):
    return UpcomingEvent(id=i, title=title, starts_at=NOW + timedelta(minutes=minutes))


def test_so_avisa_o_que_comeca_dentro_de_15_minutos_e_ainda_nao_comecou():
    eventos = [ev("a", 10), ev("b", 16), ev("c", -1), ev("d", 0), ev("e", 15), ev("", 5)]
    assert [e.id for e in due_alerts(eventos, NOW, set())] == ["d", "a", "e"]


def test_nao_repete_o_que_ja_foi_avisado():
    assert due_alerts([ev("a", 10)], NOW, {"a"}) == []


def test_texto_curto_com_minutos_e_hora():
    t, x = alert_text(ev("a", 10, "Dentista"), NOW)
    assert t == "Compromisso chegando" and "Dentista" in x and "daqui a 10 minutos" in x and "09:10" in x
    assert "agora" in alert_text(ev("a", 0, "Reunião"), NOW)[1]


class Calendario:
    def __init__(self, por_pessoa):
        self.por_pessoa, self.chamadas = por_pessoa, 0

    async def upcoming(self, user_id, within):
        self.chamadas += 1
        r = self.por_pessoa.get(user_id)
        if isinstance(r, Exception):
            raise r
        return r or []


class Avisos:
    def __init__(self, ok=True):
        self.vistos, self.ok = [], ok

    def notify(self, user_id, title, text, *, urgent=False):
        self.vistos.append((user_id, title, urgent))
        return self.ok


class Pessoas:
    def __init__(self, *ids):
        self.ids = list(ids)

    def known_users(self):
        return self.ids


class Relogio:
    def now(self):
        return NOW


def servico(cal, avisos, *ids):
    return EventAlertService(cal, avisos, Pessoas(*ids), Relogio())


def test_avisa_cada_pessoa_uma_vez_so():
    avisos = Avisos()
    s = servico(Calendario({"ana": [ev("a", 10)], "bia": [ev("a", 12)]}), avisos, "ana", "bia")
    assert asyncio.run(s.tick()) == ["a", "a"]  # o mesmo id em agendas diferentes e um aviso para cada pessoa
    assert asyncio.run(s.tick()) == []
    assert [v[0] for v in avisos.vistos] == ["ana", "bia"] and all(v[2] for v in avisos.vistos)


def test_agenda_quebrada_de_uma_pessoa_nao_atrapalha_as_outras():
    avisos = Avisos()
    s = servico(Calendario({"ana": RuntimeError("google fora"), "bia": [ev("b", 5)]}), avisos, "ana", "bia")
    assert asyncio.run(s.tick()) == ["b"]


def test_se_o_aviso_nao_foi_mostrado_tenta_de_novo_na_proxima():
    avisos = Avisos(ok=False)
    s = servico(Calendario({"ana": [ev("a", 5)]}), avisos, "ana")
    assert asyncio.run(s.tick()) == []
    avisos.ok = True
    assert asyncio.run(s.tick()) == ["a"]

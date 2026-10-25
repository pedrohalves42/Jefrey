"""Modo familia: so com consentimento, so contagens, uma oferta por semana, nunca envia sozinho."""
import asyncio
from datetime import datetime

from src.jefrey.application.family import FamilyOffer, FamilyStore
from src.jefrey.domain.family import compose, offer_due

DOMINGO_19H = datetime(2026, 10, 25, 19, 0)  # 25/10/2026 e domingo


def test_resumo_so_tem_contagens():
    t = compose("Dona Lurdes", "Ana", 2)
    assert "Dona Lurdes" in t and "2 lembretes" in t and "Oi, Ana!" in t
    assert compose("Lurdes", "Ana", 0).endswith("em dia.")
    assert "1 lembrete " in compose("Lurdes", "Ana", 1) + " "


def test_oferta_so_com_consentimento_e_contato():
    assert not offer_due(DOMINGO_19H, None, False, "Ana")
    assert not offer_due(DOMINGO_19H, None, True, "")
    assert offer_due(DOMINGO_19H, None, True, "Ana")


def test_oferta_so_domingo_a_noite_e_uma_vez():
    assert not offer_due(datetime(2026, 10, 24, 19, 0), None, True, "Ana")  # sabado
    assert not offer_due(datetime(2026, 10, 25, 10, 0), None, True, "Ana")  # domingo de manha
    assert not offer_due(DOMINGO_19H, "2026-10-25", True, "Ana")  # ja ofereceu hoje


def test_consentimento_sem_contato_nao_liga(tmp_path):
    s = FamilyStore(tmp_path / "f.json")
    assert s.set_consent("pedro", True, "  ")["enabled"] is False
    assert s.set_consent("pedro", True, "Ana")["enabled"] is True
    assert s.set_consent("pedro", False, "Ana")["enabled"] is False


def test_tick_avisa_uma_vez_e_nao_envia_nada(tmp_path):
    s = FamilyStore(tmp_path / "f.json")
    s.set_consent("pedro", True, "Ana")
    avisos = []
    job = FamilyOffer(s, users=lambda: ["pedro", "outra"], notify=lambda u, t, x: avisos.append((u, x)) or True, now=lambda: DOMINGO_19H)
    assert asyncio.run(job.tick()) == ["pedro"]
    assert asyncio.run(job.tick()) == []  # mesma semana
    assert len(avisos) == 1 and "Ana" in avisos[0][1]


def test_ferramenta_desligada_nao_monta_nada(tmp_path, monkeypatch):
    import src.jefrey.application.family as F
    from src.jefrey.skills.family import FamilySkill

    monkeypatch.setattr(F, "shared_store", lambda: FamilyStore(tmp_path / "x.json"))
    out = asyncio.run(FamilySkill().family_summary.ainvoke({"user_id": "pedro"}))
    assert "desligado" in out


def test_skill_esta_na_lista_do_app():
    from src.jefrey.skills import load_skills, skill_registry

    load_skills()
    assert skill_registry.get_tool("family_summary") is not None

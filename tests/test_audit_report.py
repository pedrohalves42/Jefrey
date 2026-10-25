"""Registro legivel: cada acao aparece com hora, nome em portugues e desfecho; nada sensivel vaza."""
from datetime import datetime

from src.jefrey.domain.audit_report import describe, summarize


def row(tool, decision="allow", approval=None, risk="low"):
    return {"tool_name": tool, "decision": decision, "approval_decision": approval, "risk": risk,
            "at": datetime(2026, 10, 11, 9, 5), "detail": {"token": "sk-secretsecretsecretsecret"}}


def test_acao_vira_frase_com_hora():
    d = describe(row("cancel_reminder"))
    assert d["hora"] == "09:05" and d["acao"] == "Cancelar lembrete" and d["desfecho"] == "feito"


def test_aprovada_negada_e_barrada():
    assert describe(row("cancel_reminder", approval="approved"))["desfecho"] == "feito com a sua aprovação"
    assert describe(row("cancel_reminder", approval="rejected"))["desfecho"] == "não aprovado"
    assert describe(row("cancel_reminder", decision="deny"))["desfecho"] == "barrado"


def test_ferramenta_desconhecida_nao_vaza_nome():
    assert describe(row("rm_rf_tudo"))["acao"] == "Ação desconhecida"


def test_resumo_conta_e_nao_traz_detalhes():
    r = summarize([row("cancel_reminder"), row("cancel_reminder", decision="deny")])
    assert r["feitos"] == 1 and r["barrados"] == 1 and "barrei 1" in r["texto"]
    assert "sk-" not in str(r)


def test_dia_vazio():
    assert summarize([])["texto"] == "Hoje eu ainda não fiz nada por você."


def test_registro_interno_fica_de_fora_mas_barrado_aparece():
    r = summarize([row("stt_transcribe"), row("rm_rf_tudo", decision="deny"), row("cancel_reminder")])
    assert r["feitos"] == 1 and r["barrados"] == 1 and len(r["itens"]) == 2

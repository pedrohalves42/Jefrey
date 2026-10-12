"""Registro legivel do que o Jefrey fez (REGRAS PURAS): transforma linhas de auditoria em frases curtas em portugues.

So entra o que importa para a pessoa: o que foi feito, o que foi barrado e o que foi pedido para ela aprovar.
Nenhum dado sensivel aparece: so o nome da acao (do catalogo), o horario e o desfecho.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Optional

from src.jefrey.domain.tool_catalog import policy_for

MAX_ITEMS = 100


def _label(tool: str) -> str:
    p = policy_for(tool)
    return p.label if p else "Ação desconhecida"


def _outcome(row: Mapping) -> str:
    decision = str(row.get("decision") or "")
    approval = str(row.get("approval_decision") or "")
    if decision == "deny":
        return "barrado"
    if approval == "approved":
        return "feito com a sua aprovação"
    if approval in ("rejected", "expired"):
        return "não aprovado"
    if decision == "hitl":
        return "esperando a sua aprovação"
    return "feito"


def describe(row: Mapping) -> dict:
    when: Optional[datetime] = row.get("at")
    return {
        "hora": when.strftime("%H:%M") if isinstance(when, datetime) else "",
        "acao": _label(str(row.get("tool_name") or "")),
        "desfecho": _outcome(row),
        "risco": str(row.get("risk") or ""),
    }


def summarize(rows: Iterable[Mapping]) -> dict:
    """{'itens': [...mais recentes primeiro], 'feitos': n, 'barrados': n, 'texto': frase para falar}."""
    itens = [describe(r) for r in list(rows)[:MAX_ITEMS]]
    feitos = sum(1 for i in itens if i["desfecho"].startswith("feito"))
    barrados = sum(1 for i in itens if i["desfecho"] == "barrado")
    if not itens:
        texto = "Hoje eu ainda não fiz nada por você."
    else:
        texto = f"Hoje eu fiz {feitos} {'coisa' if feitos == 1 else 'coisas'} por você"
        texto += f" e barrei {barrados} por segurança." if barrados else "."
    return {"itens": itens, "feitos": feitos, "barrados": barrados, "texto": texto}

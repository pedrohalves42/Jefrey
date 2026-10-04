"""Catalogo de ferramentas: risco, aprovacao e texto para humanos.

Regras (uso pessoal, FAIL-CLOSED):
  - ferramenta fora do catalogo        -> negada (nunca executa)
  - risk "low"    -> executa direto (leitura ou escrita inofensiva)
  - risk "medium" -> executa direto, com auditoria (altera dados do proprio usuario)
  - risk "high"   -> SO executa depois de aprovacao humana explicita
O modelo nunca decide o proprio nivel de risco: ele vem desta tabela.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Risk = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ToolPolicy:
    risk: Risk
    label: str  # frase curta, em portugues, para mostrar ao usuario ("Enviar e-mail")

    @property
    def needs_approval(self) -> bool:
        return self.risk == "high"


def _p(risk: Risk, label: str) -> ToolPolicy:
    return ToolPolicy(risk, label)


CATALOG: dict[str, ToolPolicy] = {
    # notas
    "save_note": _p("low", "Salvar nota"),
    "search_notes": _p("low", "Buscar nas notas"),
    "list_notes": _p("low", "Listar notas"),
    "get_note": _p("low", "Ler nota"),
    "update_note": _p("medium", "Editar nota"),
    "delete_note": _p("high", "Apagar nota"),
    # automacao
    "plan_task": _p("low", "Planejar tarefa"),
    "list_workflows": _p("low", "Listar automacoes"),
    "get_workflow": _p("low", "Ver automacao"),
    "create_workflow": _p("medium", "Criar automacao"),
    "run_workflow": _p("high", "Executar automacao"),
    "delete_workflow": _p("high", "Apagar automacao"),
    # agenda
    "list_events": _p("low", "Ver agenda"),
    "find_free_slots": _p("low", "Achar horario livre"),
    "get_calendar_list": _p("low", "Listar agendas"),
    "create_event": _p("medium", "Criar evento"),
    "update_event": _p("medium", "Alterar evento"),
    "delete_event": _p("high", "Apagar evento"),
    # e-mail
    "list_messages": _p("low", "Listar e-mails"),
    "get_message": _p("low", "Ler e-mail"),
    "search_messages": _p("low", "Buscar e-mails"),
    "list_labels": _p("low", "Listar marcadores"),
    "modify_labels": _p("medium", "Alterar marcadores"),
    "send_message": _p("high", "Enviar e-mail"),
    "reply_message": _p("high", "Responder e-mail"),
    # web
    "search": _p("low", "Buscar na web"),
    "search_news": _p("low", "Buscar noticias"),
    "extract": _p("low", "Ler pagina da web"),
    # arquivos na nuvem (Drive)
    "list_files": _p("low", "Listar arquivos do Drive"),
    "search_files": _p("low", "Buscar arquivos do Drive"),
    "get_file_metadata": _p("low", "Ver dados do arquivo"),
    "download_file": _p("medium", "Baixar arquivo do Drive"),
    "upload_file": _p("high", "Enviar arquivo ao Drive"),
    "delete_file": _p("high", "Apagar arquivo do Drive"),
    # essenciais locais
    "current_time": _p("low", "Ver data e hora"),
    "calculator": _p("low", "Calcular"),
    "weather": _p("low", "Ver o clima"),
    "files_list": _p("low", "Listar arquivos locais"),
    "files_read": _p("low", "Ler arquivo local"),
    "files_write": _p("medium", "Gravar arquivo local"),
}


def policy_for(tool_name: str) -> ToolPolicy | None:
    """None = ferramenta desconhecida: quem chama DEVE negar."""
    return CATALOG.get(tool_name)


def risk_of(tool_name: str) -> str:
    p = CATALOG.get(tool_name)
    return p.risk if p else "unknown"

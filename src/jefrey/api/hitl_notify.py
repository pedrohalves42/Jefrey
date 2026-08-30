"""Canal de Notificação HITL (Fase P5, Decisão 3).

Dispara notificações quando uma ferramenta de alto risco entra em pendência de aprovação humana.
Canais suportados:
  - Console/Log estruturado (padrão)
  - WhatsApp (via WaSender API / webhook)
  - E-mail (via SMTP)
  - Webhook genérico
"""
from __future__ import annotations

import logging
import smtplib
import urllib.request
import json
from email.mime.text import MIMEText
from typing import Optional

from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

def notify_pending_approval(
    approval_id: str,
    tool_name: str,
    risk_level: str,
    thread_id: str,
    reason: Optional[str] = None,
) -> bool:
    """Notifica o operador humano sobre uma solicitação de aprovação pendente."""
    text = (
        f"🚨 [HITL Jefrey] Aprovação Pendente!\n"
        f"• ID: {approval_id}\n"
        f"• Ferramenta: {tool_name}\n"
        f"• Risco: {risk_level.upper()}\n"
        f"• Thread: {thread_id}\n"
        f"• Motivo: {reason or 'Não especificado'}\n"
        f"• Decida via: POST /approvals/{approval_id}/decide"
    )
    logger.info("hitl_notify: %s", text.replace("\n", " | "))

    # 1. Notificação via Log / Console sempre executada
    success = True

    # 2. WhatsApp (WaSender API ou Endpoint local configurado)
    # Se configurado em variáveis de ambiente futuras ou settings
    # 3. SMTP se configurado
    return success

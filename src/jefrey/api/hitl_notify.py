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
import os
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
    """Notifica o operador humano sobre uma solicitação de aprovação pendente.

    Canais: log (sempre), WhatsApp (se WASENDER_API_KEY configurado),
    SMTP (se SMTP_HOST configurado), webhook (se HITL_WEBHOOK_URL configurado).
    """
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

    success = True

    # WhatsApp (WaSender)
    wasender_key = os.environ.get("WASENDER_API_KEY")
    if wasender_key:
        try:
            _notify_whatsapp(wasender_key, text)
        except Exception as e:
            logger.warning("hitl_notify: falha WhatsApp: %s", e)
            success = False

    # SMTP
    smtp_host = os.environ.get("SMTP_HOST")
    if smtp_host:
        try:
            _notify_smtp(smtp_host, text, approval_id)
        except Exception as e:
            logger.warning("hitl_notify: falha SMTP: %s", e)
            success = False

    # Webhook genérico
    webhook_url = os.environ.get("HITL_WEBHOOK_URL")
    if webhook_url:
        try:
            _notify_webhook(webhook_url, approval_id, tool_name, risk_level, thread_id)
        except Exception as e:
            logger.warning("hitl_notify: falha webhook: %s", e)
            success = False

    return success


def _notify_whatsapp(api_key: str, text: str) -> None:
    """Envia notificação via WaSender API."""
    # Placeholder — implementar com a API real do WaSender quando configurado
    logger.info("hitl_notify: WhatsApp enviado (placeholder — API key presente)")


def _notify_smtp(host: str, text: str, approval_id: str) -> None:
    """Envia notificação via SMTP."""
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_to = os.environ.get("SMTP_TO", smtp_user)

    if not smtp_user or not smtp_pass:
        logger.warning("hitl_notify: SMTP configurado mas SMTP_USER/SMTP_PASS ausentes")
        return

    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = f"[Jefrey HITL] Aprovação Pendente — {approval_id[:8]}"
    msg["From"] = smtp_user
    msg["To"] = smtp_to

    with smtplib.SMTP(host, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [smtp_to], msg.as_string())
    logger.info("hitl_notify: email enviado para %s", smtp_to)


def _notify_webhook(url: str, approval_id: str, tool_name: str, risk_level: str, thread_id: str) -> None:
    """Envia notificação via webhook POST."""
    payload = json.dumps({
        "type": "hitl_approval_pending",
        "approval_id": approval_id,
        "tool_name": tool_name,
        "risk_level": risk_level,
        "thread_id": thread_id,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        logger.info("hitl_notify: webhook enviado, status=%d", resp.status)

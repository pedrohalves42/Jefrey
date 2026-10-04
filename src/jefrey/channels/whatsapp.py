"""WhatsApp Cloud API (oficial, da Meta): configuracao, assinatura do webhook, leitura e envio.

Seguranca:
  - sem app secret configurado, NENHUM webhook e aceito (fail-closed);
  - a assinatura X-Hub-Signature-256 e conferida sobre o corpo bruto, em tempo constante;
  - so numeros da lista de autorizados falam com o Jefrey (os demais sao ignorados em silencio).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

import httpx

from src.jefrey.channels.base import InboundMessage, split_message

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com"
_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """'+55 (11) 99999-0000' -> '5511999990000'."""
    return _DIGITS.sub("", raw or "")


@dataclass(frozen=True)
class WhatsAppConfig:
    enabled: bool = False
    verify_token: str = ""
    app_secret: str = ""
    access_token: str = ""
    phone_number_id: str = ""
    api_version: str = "v21.0"
    # numero autorizado (so digitos) -> user_id do Jefrey
    allowed: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "WhatsAppConfig":
        e = env if env is not None else os.environ
        allowed: dict[str, str] = {}
        # formato: "5511999990000=demo,5521988887777=ana" (so o numero => usuario "demo")
        for item in (e.get("JEFREY_WHATSAPP__ALLOWED") or "").split(","):
            item = item.strip()
            if not item:
                continue
            phone, _, user = item.partition("=")
            phone = normalize_phone(phone)
            if phone:
                allowed[phone] = (user.strip() or "demo")
        return cls(
            enabled=(e.get("JEFREY_WHATSAPP__ENABLED") or "").strip().lower() in ("1", "true", "yes"),
            verify_token=e.get("JEFREY_WHATSAPP__VERIFY_TOKEN", ""),
            app_secret=e.get("JEFREY_WHATSAPP__APP_SECRET", ""),
            access_token=e.get("JEFREY_WHATSAPP__ACCESS_TOKEN", ""),
            phone_number_id=e.get("JEFREY_WHATSAPP__PHONE_NUMBER_ID", ""),
            api_version=e.get("JEFREY_WHATSAPP__API_VERSION", "v21.0") or "v21.0",
            allowed=allowed,
        )

    @property
    def ready(self) -> bool:
        """Pronto para receber: ligado e com os segredos minimos (senao fica fechado)."""
        return bool(self.enabled and self.verify_token and self.app_secret and self.allowed)

    @property
    def can_send(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    def user_for(self, sender: str) -> Optional[str]:
        return self.allowed.get(normalize_phone(sender))


# ---------------------------------------------------------------- webhook
def verify_signature(app_secret: str, body: bytes, header: Optional[str]) -> bool:
    """X-Hub-Signature-256 = 'sha256=' + HMAC-SHA256(app_secret, corpo bruto). Fail-closed."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):].strip().lower())


def check_challenge(cfg: WhatsAppConfig, params: Mapping[str, str]) -> Optional[str]:
    """Handshake de configuracao do webhook (GET). Devolve o desafio, ou None se invalido."""
    if not cfg.verify_token:
        return None
    if params.get("hub.mode") == "subscribe" and hmac.compare_digest(
        str(params.get("hub.verify_token", "")), cfg.verify_token
    ):
        challenge = str(params.get("hub.challenge", ""))
        return challenge if challenge else None
    return None


def _d(x: Any) -> dict:
    """So aceita dicionarios; qualquer outra coisa vira {} (payload malformado nao quebra o parser)."""
    return x if isinstance(x, dict) else {}


def parse_webhook(payload: Any, expected_phone_number_id: str = "") -> list[InboundMessage]:
    """Extrai mensagens recebidas. Ignora recibos de entrega e qualquer formato inesperado."""
    out: list[InboundMessage] = []
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return out
    def items(x: Any) -> list:
        return [i for i in x if isinstance(i, dict)] if isinstance(x, list) else []

    for entry in items(payload.get("entry")):
        for change in items(entry.get("changes")):
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            meta = value.get("metadata")
            meta_id = str(meta.get("phone_number_id") or "") if isinstance(meta, dict) else ""
            if expected_phone_number_id and meta_id and meta_id != expected_phone_number_id:
                continue  # mensagem para outro numero
            for m in items(value.get("messages")):
                sender = normalize_phone(str(m.get("from") or ""))
                mid = str(m.get("id") or "")
                if not sender or not mid:
                    continue
                kind = str(m.get("type") or "other")
                text = ""
                if kind == "text":
                    text = str(_d(m.get("text")).get("body") or "")
                elif kind == "button":
                    text = str(_d(m.get("button")).get("text") or "")
                    kind = "text"
                elif kind == "interactive":
                    inter = _d(m.get("interactive"))
                    reply = _d(inter.get("button_reply")) or _d(inter.get("list_reply"))
                    text = str(reply.get("title") or "")
                    kind = "text"
                elif kind not in ("audio", "image"):
                    kind = "other"
                out.append(InboundMessage("whatsapp", sender, mid, text.strip(), kind))
    return out


# ---------------------------------------------------------------- envio
class WhatsAppClient:
    """Envia texto pela Cloud API. Implementa o protocolo Channel."""

    def __init__(self, cfg: WhatsAppConfig, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.cfg = cfg
        self._transport = transport

    async def send_text(self, to: str, text: str) -> None:
        if not self.cfg.can_send:
            logger.warning("whatsapp: envio desligado (faltam ACCESS_TOKEN/PHONE_NUMBER_ID)")
            return
        url = f"{GRAPH_URL}/{self.cfg.api_version}/{self.cfg.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.cfg.access_token}"}
        async with httpx.AsyncClient(timeout=20, transport=self._transport) as client:
            for part in split_message(text):
                body = {"messaging_product": "whatsapp", "to": normalize_phone(to), "type": "text",
                        "text": {"body": part, "preview_url": False}}
                r = await client.post(url, headers=headers, json=body)
                if r.status_code >= 400:
                    # nunca registra o token nem o texto do usuario
                    logger.warning("whatsapp: envio falhou HTTP %s", r.status_code)
                    r.raise_for_status()

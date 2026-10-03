"""Guarda de conteúdo mínimo (base para P7).

Previne que o output de ferramentas MCP externas seja interpretado pelo LLM como
instrução (prompt injection). Padrões conhecidos de injeção são bloqueados antes
de o conteúdo chegar ao modelo.

M2 — redact PII antes de logar ou retornar ao LLM (Security Eng ch.8)
M3 — Fernet-based PII/credential masking for output (CIPHER-031)
"""
from __future__ import annotations

import logging
import os
import re
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# M3: Fernet key from env (set in .env for production); fallback to None means redaction-only mode
FERNET_KEY = os.getenv("JEFREY_FERNET_KEY")
if FERNET_KEY:
    fernet = Fernet(FERNET_KEY.encode())
else:
    fernet = None

# M2 — redact PII antes de logar ou retornar ao LLM (Security Eng ch.8)
_PII_RE = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._\-]+|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}|cpf\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2})",
    re.IGNORECASE,
)

def redact_pii(s: str) -> str:
    return _PII_RE.sub("[REDACTED]", s)

# M3: Fernet-based PII/credential masking for output (CIPHER-031)
def mask_sensitive_data(content: str) -> str:
    """Mask PII and credentials using Fernet encryption for secure storage/transmission.

    If FERNET_KEY is set, encrypts the masked content.
    If no key, falls back to redaction only.

    Patterns masked (before encryption):
    - sk-... : OpenAI API keys
    - Bearer ... : Bearer tokens
    - email addresses
    """
    if not content:
        return content

    # Fallback: redact if no fernet key
    if not fernet:
        return redact_pii(content)

    # Patterns to mask before encryption
    patterns = [
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API keys
        r"Bearer [a-zA-Z0-9._\-]+",  # Bearer tokens
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",  # Email addresses
    ]

    masked = content
    for pattern in patterns:
        masked = re.sub(pattern, "[REDACTED]", masked)

    try:
        return fernet.encrypt(masked.encode()).decode()
    except Exception:
        # If encryption fails, fall back to redaction
        return masked


# M4: Sanitização de output de ferramentas (agent.py espera esta funcao)
def sanitize_tool_output(content: str, source: str = "") -> str:
    """Sanitiza output de ferramenta antes de entregar ao LLM/agent.

    Aplica:
    1. Redação de PII/credenciais (mask_sensitive_data)
    2. Bloqueio de padrões de prompt injection conhecidos
    3. Limite de tamanho (8000 chars)

    Args:
        content: Texto bruto da ferramenta
        source: Identificador da fonte (ex: "mcp:server:tool")

    Returns:
        Texto sanitizado seguro para LLM
    """
    if not content:
        return content

    # 1. PII/credential masking
    sanitized = mask_sensitive_data(content)

    # 2. Prompt injection patterns (OWASP LLM Top 10)
    injection_patterns = [
        r"(?i)ignore\s+(previous|all)\s+instructions",
        r"(?i)disregard\s+(previous|all)\s+instructions",
        r"(?i)system\s*:\s*you\s+are\s+now",
        r"(?i)new\s+instructions\s*:",
        r"(?i)forget\s+everything",
        r"(?i)override\s+safety",
        r"(?i)jailbreak",
        r"(?i)pretend\s+to\s+be",
        r"(?i)roleplay\s+as",
        r"(?i)simulate\s+being",
        r"(?i)you\s+are\s+now\s+(?:an?|the)\s+\w+",      # "You are now a..."
        r"(?i)act\s+as\s+(?:an?|the)\s+\w+",              # "Act as a..."
        r"(?i)from\s+now\s+on\s+you\s+(?:are|will)",      # "From now on you..."
        r"(?i)your\s+(?:new|real)\s+(?:role|persona|identity)",  # "Your new role..."
        r"(?i)bypass\s+(?:all\s+)?(?:safety|security|filters?)", # "Bypass safety..."
        r"(?i)disable\s+(?:all\s+)?(?:safety|security|filters?)", # "Disable safety..."
        r"(?i)ignore\s+(?:all\s+)?(?:rules|guidelines|constraints?)", # "Ignore rules..."
        r"(?i)you\s+don't\s+need\s+to\s+(?:follow|obey)", # "You don't need to follow..."
        r"(?i)pretend\s+(?:that\s+)?you\s+(?:don't|do\s+not)", # "Pretend you don't..."
        r"(?i)as\s+an\s+ai\s+(?:language\s+)?model\s*,?\s*i\s+(?:cannot|won't|refuse)", # "As an AI model, I cannot..."
    ]
    # Additional patterns for test coverage
    injection_patterns += [
        r"(?i)forget\s+all\s+rules",
        r"(?i)forget\s+all\s+and\s+output",
        r"(?i)###\s*system\s*:",
        r"(?i)#\s*system\s*:",
        r"(?i)###\s*system\b",  # matches ###system or ### system without colon
        r"(?i)system\s*:\s*new\s+instructions",
        r"(?i)reveal\s+(?:all\s+)?(?:secrets?|prompts?|instructions?)",
        r"(?i)output\s+(?:the\s+)?(?:system\s+)?(?:prompt|instructions?)",
        r"(?i)show\s+(?:me\s+)?(?:the\s+)?(?:system\s+)?(?:prompt|instructions?)",
    ]
    for pattern in injection_patterns:
        sanitized = re.sub(pattern, "[BLOQUEADO]", sanitized)

    # 3. Size limit (prevent context flooding)
    MAX_TOOL_OUTPUT = 8000
    if len(sanitized) > MAX_TOOL_OUTPUT:
        logger.warning("Tool output truncated: %s (len=%d)", source, len(sanitized))
        sanitized = sanitized[:MAX_TOOL_OUTPUT] + "\n...[TRUNCATED]..."

    return sanitized
"""Guarda de conteudo minimo (base para P7).

Previne que o output de ferramentas MCP externas seja interpretado pelo LLM como
instrucao (prompt injection). Padroes conhecidos de injecao sao bloqueados antes
de o conteudo chegar ao modelo.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)
# M2 — redact PII antes de logar ou retornar ao LLM (Security Eng ch.8)
_PII_RE = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._\-]+|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}|cpf\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2})",
    re.IGNORECASE,
)

def redact_pii(s: str) -> str:
    return _PII_RE.sub("[REDACTED]", s)


# Padroes que indicam tentativa de prompt injection no conteudo retornado.
_INJECTION_PATTERNS: list[str] = [
    # --- Prompt injection classico ---
    r"ignore (previous|prior|all) instructions",
    r"disregard (previous|prior|all)",
    r"forget (previous|prior|all)",
    r"override (previous|prior|all) (instructions|rules|prompts)",
    r"new instructions:",
    r"you are now",
    r"act as (a |an )?",
    r"pretend (you are|to be)",
    r"roleplay as",
    r"repeat after me",
    r"do the following",
    r"BEGIN:INSTRUCTION",

    # --- Delimitadores de sistema / formatacao de treino ---
    r"system prompt",
    r"###\s*(Human|Assistant|System):",
    # FIX: label de fine-tuning so e perigoso no INICIO de linha (não no meio do texto)
    r"^(Human|Assistant|System):",
    r"^(SYSTEM|USER|ASSISTANT):",

    # --- Tokens especiais de modelo (ChatML, Llama, Cohere, etc.) ---
    r"<\|.*?\|>",                       # genericos <|...|>
    r"<\|im_start\|>",                  # ChatML
    r"<\|im_end\|>",
    r"<\|endoftext\|>",                 # GPT
    r"<s>",                             # BOS Llama/Mistral
    r"</s>",                            # EOS Llama/Mistral
    r"\[INST\]",                        # Llama instruction tags
    r"\[/INST\]",
    r"<<SYS>>",                         # Llama2 chat format

    # --- Template injection ---
    r"\{\{.*system.*\}\}",              # Jinja/template injection
    r"\{system\}",                      # Template syntax

    # --- Padding / obfuscacao ---
    r"^\s{20,}",                        # muitos espacos no inicio (ocultar texto)
]

def sanitize_tool_output(content: str, source: str = "external") -> str:
    """Sanitiza output de ferramenta externa antes de passar ao LLM.

    M2: redact_pii antes de injection check e log para nao vazar PII (Security Eng).
    Retorna o conteudo original (redigido) se seguro, ou marcador se bloqueado.
    """
    if not content:
        return content
    # M2: redact PII antes de qualquer processamento/log
    try:
        content = redact_pii(content)
    except Exception as e:
        logger.warning("content_guard redact_pii falhou: %s", e)
    for pattern in _INJECTION_PATTERNS:
        # FIX: usa re.MULTILINE para que ^ funcione por linha (evita falsos positivos
        # de "Human:" no meio de texto normal)
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            logger.warning(
                "content_guard.blocked source=%s pattern=%s preview=%s",
                source, pattern, content[:100],
            )
            return f"[CONTEUDO BLOQUEADO: output de '{source}' contem padrao suspeito]"
    # SECURITY (P0.5): log de passes bem-sucedidos para auditoria de tentativas
    logger.debug("content_guard.pass source=%s len=%d", source, len(content))
    return content

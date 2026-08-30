"""Guarda de conteúdo mínimo (base para P7).

Previne que o output de ferramentas MCP externas seja interpretado pelo LLM como
instrução (prompt injection). Padrões conhecidos de injeção são bloqueados antes
de o conteúdo chegar ao modelo.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Padrões que indicam tentativa de prompt injection no conteúdo retornado.
_INJECTION_PATTERNS: list[str] = [
    # --- Prompt injection clássico ---
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

    # --- Delimitadores de sistema / formatação de treino ---
    r"system prompt",
    r"###\s*(Human|Assistant|System):",
    r"(Human|Assistant|System):",       # labels OpenAI fine-tuning (sem ###)
    r"SYSTEM:",                         # uppercase labels
    r"USER:",
    r"ASSISTANT:",

    # --- Tokens especiais de modelo (ChatML, Llama, Cohere, etc.) ---
    r"<\|.*?\|>",                       # tokens genéricos <|...|>
    r"<\|im_start\|>",                  # ChatML
    r"<\|im_end\|>",
    r"<\|endoftext\|>",                 # GPT
    r"<s>",                             # BOS Llama/Mistral
    r"</s>",                            # EOS Llama/Mistral
    r"\[INST\]",                        # Llama instruction tags
    r"\[/INST\]",
    r"<<SYS>>",                         # Llama2 chat format
    r"</s>",

    # --- Template injection ---
    r"\{\{.*system.*\}\}",              # Jinja/template injection
    r"\{system\}",                      # Template syntax

    # --- Padding / obfuscação ---
    r"^\s{20,}",                        # muitos espaços no início (ocultar texto)
]


def sanitize_tool_output(content: str, source: str = "external") -> str:
    """Sanitiza output de ferramenta externa antes de passar ao LLM.

    Retorna o conteúdo original se seguro, ou um marcador de bloqueio se contiver
    padrão suspeito de injeção de prompt.
    """
    if not content:
        return content
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            logger.warning(
                "content_guard.blocked source=%s pattern=%s preview=%s",
                source, pattern, content[:100],
            )
            return f"[CONTEÚDO BLOQUEADO: output de '{source}' contém padrão suspeito]"
    # SECURITY (P0.5): log de passes bem-sucedidos para auditoria de tentativas
    logger.debug("content_guard.pass source=%s len=%d", source, len(content))
    return content

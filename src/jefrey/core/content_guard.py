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
    r"ignore (previous|prior|all) instructions",
    r"system prompt",
    r"you are now",
    r"new instructions:",
    r"<\|.*?\|>",          # tokens especiais de modelo
    r"\[INST\]",           # Llama instruction tags
    r"###\s*(Human|Assistant|System):",
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
    return content

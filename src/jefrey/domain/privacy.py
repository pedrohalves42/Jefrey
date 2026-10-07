"""Seus dados (LGPD): ver o que o Jefrey guarda, baixar uma copia e apagar tudo.

"Apagar tudo" remove os dados PESSOAIS da pessoa (nome, conversas, fatos, diario, estudos, resumos, lembretes, notas e memorias,
WhatsApp e conexoes com o Google). Nao remove a escolha da inteligencia (modelo/chave), que e do programa e nao da pessoa.
Registros de seguranca (auditoria de aprovacoes) ficam: nao tem o texto das conversas.
"""
from __future__ import annotations

import re

TERMS_VERSION = "2026-10-04"


def strip_review_comments(text: str) -> str:
    """Tira os comentarios internos de revisao dos textos legais antes de mostrar."""
    return re.sub(r"<!--.*?-->\s*", "", text, flags=re.S).strip()

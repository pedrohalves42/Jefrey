"""Erros cuja mensagem ja e clara e segura para mostrar a pessoa (o resto vira um texto generico)."""
from __future__ import annotations


class UserFacingError(RuntimeError):
    """A mensagem pode ser mostrada como esta."""

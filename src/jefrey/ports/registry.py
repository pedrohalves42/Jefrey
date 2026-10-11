"""Registro das portas: a raiz de composicao (`bootstrap.wire`) diz QUEM implementa cada porta; os casos de uso pedem pelo nome.

`use(nome)` devolve a implementacao registrada. Se ainda nao ha nenhuma, liga os adaptadores padrao (bootstrap.wire) e tenta de novo.
Testes trocam uma porta com `provide(nome, falso)` e desfazem com `reset()`.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable

_impl: dict[str, Any] = {}
_wired = False


def provide(name: str, impl: Any) -> None:
    _impl[name] = impl


def _wire() -> None:
    global _wired
    if not _wired:
        _wired = True
        importlib.import_module("src.jefrey.bootstrap").wire()


def use(name: str) -> Any:
    if name not in _impl:
        _wire()
    try:
        return _impl[name]
    except KeyError:
        raise LookupError(f"nenhum adaptador registrado para a porta '{name}'") from None


def reset(names: "list[str] | None" = None) -> None:
    """Esquece o registro (todo ou so `names`); o proximo `use` liga os padroes de novo."""
    global _wired
    for n in list(_impl) if names is None else names:
        _impl.pop(n, None)
    _wired = False


def default(name: str, factory: Callable[[], Any]) -> None:
    """Registra `factory()` so se a porta ainda nao tem implementacao (o padrao nao atropela um falso de teste)."""
    if name not in _impl:
        _impl[name] = factory()

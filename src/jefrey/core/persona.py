"""Atalho de compatibilidade: este modulo agora mora em domain/persona.py."""
import sys

from src.jefrey.domain import persona as _moved

sys.modules[__name__] = _moved

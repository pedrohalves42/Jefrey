"""Atalho de compatibilidade: este modulo agora mora em domain/halt.py."""
import sys

from src.jefrey.domain import halt as _moved

sys.modules[__name__] = _moved

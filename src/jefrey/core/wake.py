"""Atalho de compatibilidade: este modulo agora mora em domain/wake.py."""
import sys

from src.jefrey.domain import wake as _moved

sys.modules[__name__] = _moved

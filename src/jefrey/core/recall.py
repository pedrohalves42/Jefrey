"""Atalho de compatibilidade: este modulo agora mora em domain/recall.py."""
import sys

from src.jefrey.domain import recall as _moved

sys.modules[__name__] = _moved

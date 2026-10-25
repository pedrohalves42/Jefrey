"""Atalho de compatibilidade: este modulo agora mora em domain/framing.py."""
import sys

from src.jefrey.domain import framing as _moved

sys.modules[__name__] = _moved

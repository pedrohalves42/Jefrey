"""Atalho de compatibilidade: este modulo agora mora em domain/wakeword.py."""
import sys

from src.jefrey.domain import wakeword as _moved

sys.modules[__name__] = _moved

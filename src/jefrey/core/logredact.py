"""Atalho de compatibilidade: este modulo agora mora em domain/logredact.py."""
import sys

from src.jefrey.domain import logredact as _moved

sys.modules[__name__] = _moved

"""Atalho de compatibilidade: este modulo agora mora em domain/policy.py."""
import sys

from src.jefrey.domain import policy as _moved

sys.modules[__name__] = _moved

"""Atalho de compatibilidade: este modulo agora mora em domain/registry.py."""
import sys

from src.jefrey.domain import registry as _moved

sys.modules[__name__] = _moved

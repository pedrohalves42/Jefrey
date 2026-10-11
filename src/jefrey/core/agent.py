"""Atalho de compatibilidade: este modulo agora mora em application/agent.py."""
import sys

from src.jefrey.application import agent as _moved

sys.modules[__name__] = _moved

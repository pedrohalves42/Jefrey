"""Atalho de compatibilidade: este modulo agora mora em application/agent_loop.py."""
import sys

from src.jefrey.application import agent_loop as _moved

sys.modules[__name__] = _moved

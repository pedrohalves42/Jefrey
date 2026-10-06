"""Atalho de compatibilidade: este modulo agora mora em domain/llm_tools.py."""
import sys

from src.jefrey.domain import llm_tools as _moved

sys.modules[__name__] = _moved

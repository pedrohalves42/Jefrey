"""Atalho de compatibilidade: este modulo agora mora em domain/tool_catalog.py."""
import sys

from src.jefrey.domain import tool_catalog as _moved

sys.modules[__name__] = _moved

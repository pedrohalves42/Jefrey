"""Atalho de compatibilidade: este modulo agora mora em application/tool_runtime.py."""
import sys

from src.jefrey.application import tool_runtime as _moved

sys.modules[__name__] = _moved

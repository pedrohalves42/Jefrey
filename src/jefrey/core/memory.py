"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/memory.py."""
import sys

from src.jefrey.adapters.outbound import memory as _moved

sys.modules[__name__] = _moved

"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/pg_memory.py."""
import sys

from src.jefrey.adapters.outbound import pg_memory as _moved

sys.modules[__name__] = _moved

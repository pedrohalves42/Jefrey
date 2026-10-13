"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/pg_memory_ttl.py."""
import sys

from src.jefrey.adapters.outbound import pg_memory_ttl as _moved

sys.modules[__name__] = _moved

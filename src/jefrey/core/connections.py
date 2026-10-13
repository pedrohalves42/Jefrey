"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/connections.py."""
import sys

from src.jefrey.adapters.outbound import connections as _moved

sys.modules[__name__] = _moved

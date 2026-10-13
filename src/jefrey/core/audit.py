"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/audit.py."""
import sys

from src.jefrey.adapters.outbound import audit as _moved

sys.modules[__name__] = _moved

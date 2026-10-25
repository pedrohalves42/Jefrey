"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/rate_limit.py."""
import sys

from src.jefrey.adapters.outbound import rate_limit as _moved

sys.modules[__name__] = _moved

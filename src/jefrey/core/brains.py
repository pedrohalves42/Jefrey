"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/brains.py."""
import sys

from src.jefrey.adapters.outbound import brains as _moved

sys.modules[__name__] = _moved

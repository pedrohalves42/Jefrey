"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/availability.py."""
import sys

from src.jefrey.adapters.outbound import availability as _moved

sys.modules[__name__] = _moved

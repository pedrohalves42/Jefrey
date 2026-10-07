"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/profile.py."""
import sys

from src.jefrey.adapters.outbound import profile as _moved

sys.modules[__name__] = _moved

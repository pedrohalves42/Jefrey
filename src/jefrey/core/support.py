"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/support.py."""
import sys

from src.jefrey.adapters.outbound import support as _moved

sys.modules[__name__] = _moved

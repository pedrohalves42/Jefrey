"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/localvoice.py."""
import sys

from src.jefrey.adapters.outbound import localvoice as _moved

sys.modules[__name__] = _moved

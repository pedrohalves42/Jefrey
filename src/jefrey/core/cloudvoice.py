"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/cloudvoice.py."""
import sys

from src.jefrey.adapters.outbound import cloudvoice as _moved

sys.modules[__name__] = _moved

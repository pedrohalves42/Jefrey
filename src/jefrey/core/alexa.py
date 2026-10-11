"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/alexa.py."""
import sys

from src.jefrey.adapters.outbound import alexa as _moved

sys.modules[__name__] = _moved

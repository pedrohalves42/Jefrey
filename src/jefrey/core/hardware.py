"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/hardware.py."""
import sys

from src.jefrey.adapters.outbound import hardware as _moved

sys.modules[__name__] = _moved

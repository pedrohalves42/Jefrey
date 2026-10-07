"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/config.py."""
import sys

from src.jefrey.adapters.outbound import config as _moved

sys.modules[__name__] = _moved

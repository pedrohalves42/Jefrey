"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/history.py."""
import sys

from src.jefrey.adapters.outbound import history as _moved

sys.modules[__name__] = _moved

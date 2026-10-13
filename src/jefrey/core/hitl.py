"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/hitl.py."""
import sys

from src.jefrey.adapters.outbound import hitl as _moved

sys.modules[__name__] = _moved

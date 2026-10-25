"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/metrics.py."""
import sys

from src.jefrey.adapters.outbound import metrics as _moved

sys.modules[__name__] = _moved

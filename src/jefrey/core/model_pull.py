"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/model_pull.py."""
import sys

from src.jefrey.adapters.outbound import model_pull as _moved

sys.modules[__name__] = _moved

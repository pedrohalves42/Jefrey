"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/checkpointer.py."""
import sys

from src.jefrey.adapters.outbound import checkpointer as _moved

sys.modules[__name__] = _moved

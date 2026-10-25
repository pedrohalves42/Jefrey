"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/diary.py."""
import sys

from src.jefrey.adapters.outbound import diary as _moved

sys.modules[__name__] = _moved

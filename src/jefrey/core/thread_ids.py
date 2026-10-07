"""Atalho de compatibilidade: este modulo agora mora em domain/thread_ids.py."""
import sys

from src.jefrey.domain import thread_ids as _moved

sys.modules[__name__] = _moved
